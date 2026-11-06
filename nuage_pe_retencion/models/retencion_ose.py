# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
"""Envío del comprobante de retención electrónico (UBL 2.0, tipo 20) a la OSE.

Reutiliza de solse_pe_cpe lo mismo que usan las facturas: el certificado de la
compañía, el servidor OSE (URL, usuario y clave), la firma `get_sign_document`
y el cliente SOAP `send_sunat_cpe`. No modifica nada de Solse.
"""
import base64
import logging
import re
import zipfile
from io import BytesIO

from lxml import etree
from pysimplesoap.client import SoapClient

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from . import retencion_xml as rx

_logger = logging.getLogger(__name__)

# El cron reintenta cada 15 minutos: 12 intentos ≈ 3 horas de caída de la OSE.
# El botón «Enviar a la OSE» reinicia el contador.
MAX_INTENTOS = 12


class NuageRetencionOse(models.Model):
    _inherit = 'nuage.retencion'

    ose_estado = fields.Selection([
        ('pendiente', 'Pendiente de envío'),
        ('aceptado', 'Aceptado por SUNAT'),
        ('observado', 'Aceptado con observaciones'),
        ('rechazado', 'Rechazado'),
        ('omitido', 'No enviado (anterior a la integración)'),
    ], string='Estado en la OSE', default='pendiente', copy=False, tracking=True, index=True)
    ose_codigo = fields.Char('Código de respuesta', copy=False, readonly=True)
    ose_respuesta = fields.Char('Respuesta', copy=False, readonly=True)
    ose_nota = fields.Text('Observaciones de SUNAT', copy=False, readonly=True)
    ose_fecha_envio = fields.Datetime('Fecha del último envío', copy=False, readonly=True)
    ose_intentos = fields.Integer('Intentos de envío', copy=False, readonly=True)
    ose_xml_firmado = fields.Binary('XML firmado', copy=False, readonly=True, attachment=True)
    ose_xml_fname = fields.Char('Nombre del XML', copy=False, readonly=True)
    ose_cdr = fields.Binary('CDR (constancia de recepción)', copy=False, readonly=True, attachment=True)
    ose_cdr_fname = fields.Char('Nombre del CDR', copy=False, readonly=True)
    ose_digest = fields.Char('Digest de la firma', copy=False, readonly=True)

    # ------------------------------------------------------------------ datos
    def _ose_empresa(self):
        """La compañía con las credenciales (la matriz, igual que solse.cpe.obtener_empresa)."""
        self.ensure_one()
        empresa = self.company_id.parent_id or self.company_id
        return empresa.sudo()

    @staticmethod
    def _ose_direccion(partner):
        distrito = getattr(partner, 'l10n_pe_district', False)
        ubigeo = (distrito and distrito.code or '').strip()
        return {
            'ubigeo': ubigeo if re.fullmatch(r'\d{6}', ubigeo) else '',
            'calle': partner.street or '',
            'urbanizacion': partner.street2 or '',
            'provincia': (getattr(partner, 'city_id', False) and partner.city_id.name) or partner.city or '',
            'departamento': (partner.state_id and partner.state_id.name) or '',
            'distrito': (distrito and distrito.name) or '',
        }

    @staticmethod
    def _ose_nombre_legal(partner):
        legal = (getattr(partner, 'legal_name', '') or '').strip()
        return legal if legal and legal != '-' else (partner.name or '')

    def _ose_datos(self):
        self.ensure_one()
        empresa = self._ose_empresa()
        agente = empresa.partner_id
        proveedor = self.partner_id.commercial_partner_id
        documentos = []
        for linea in self.line_ids:
            move = linea.move_id
            moneda = linea.moneda_origen_id.name or 'PEN'
            documentos.append({
                'tipo': move.l10n_latam_document_type_id.code,
                'serie_numero': (move.l10n_latam_document_number or '').strip().upper(),
                'fecha_emision': linea.fecha_emision or move.invoice_date,
                'moneda': moneda,
                'importe_total': linea.importe_operacion,
                'pago_nro': linea.nro_pago or 1,
                'pago_importe': linea.importe_pago,
                'pago_fecha': linea.fecha_pago,
                'retencion': linea.importe_retenido,
                'retencion_fecha': linea.fecha_pago,
                'neto': linea.importe_neto,
                'tipo_cambio': linea.tipo_cambio if moneda != 'PEN' else None,
            })
        return {
            'serie_numero': self.name,
            'fecha_emision': self.date,
            'agente': {
                'ruc': (agente.doc_number or '').strip(),
                'razon_social': self._ose_nombre_legal(agente),
                'nombre_comercial': getattr(agente, 'commercial_name', ''),
                'direccion': self._ose_direccion(agente),
            },
            'proveedor': {
                'ruc': (proveedor.doc_number or '').strip(),
                'razon_social': self._ose_nombre_legal(proveedor),
            },
            'codigo_regimen': rx.CODIGO_REGIMEN_TASA_3,
            'tasa': self.tasa,
            'nota': self.observaciones,
            'moneda': 'PEN',
            'total_retenido': self.importe_retenido,
            'total_pagado': self.importe_neto,
            'documentos': documentos,
        }

    # ------------------------------------------------------- generar y firmar
    def _ose_generar(self):
        """Arma el XML y lo firma con el certificado de la compañía."""
        self.ensure_one()
        from odoo.addons.solse_pe_cpe.models.cpe_core import get_sign_document
        if self.state != 'emitido':
            raise UserError(_('Solo se puede generar el XML de un comprobante emitido.'))
        if self.ose_estado in ('aceptado', 'observado'):
            raise UserError(_('El comprobante %s ya fue aceptado por SUNAT.') % self.name)
        empresa = self._ose_empresa()
        if not empresa.pe_certificate_id:
            raise UserError(_('No se ha establecido un certificado digital. '
                              'Revise la configuración de la empresa.'))
        try:
            xml = rx.construir_xml(self._ose_datos())
        except ValueError as e:
            raise UserError(_('No se puede generar el XML de %(nombre)s:\n%(detalle)s',
                              nombre=self.name, detalle=e))
        certificado = empresa.pe_certificate_id.sudo()
        firmado = get_sign_document(xml.decode('utf-8'), certificado.key, certificado.crt)
        digest = etree.fromstring(firmado).find('.//{%s}DigestValue' % rx.NS_DS)
        self.write({
            'ose_xml_firmado': base64.b64encode(firmado),
            'ose_xml_fname': '%s.xml' % rx.nombre_archivo(empresa.partner_id.doc_number, self.name),
            'ose_digest': digest.text if digest is not None else False,
        })

    def _ose_aviso_ya_enviado(self):
        """Aviso amable (y recarga) si el envío automático ya se completó antes del clic."""
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {
                'title': _('Ya enviado a la OSE'),
                'message': _('El comprobante %s ya fue enviado automáticamente: %s. '
                             'Se actualizó la pantalla.') % (
                    ', '.join(self.mapped('name')),
                    ', '.join(dict(self._fields['ose_estado'].selection).get(e, e)
                              for e in set(self.mapped('ose_estado')))),
                'type': 'info', 'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    def action_ose_generar(self):
        enviados = self.filtered(lambda r: r.ose_estado in ('aceptado', 'observado'))
        for rec in self - enviados:
            rec._ose_generar()
        return enviados._ose_aviso_ya_enviado() if enviados else True

    # ----------------------------------------------------------------- enviar
    @staticmethod
    def _ose_leer_cdr(cdr_b64):
        """(codigo, descripcion, notas) del CDR (ZIP con el XML de respuesta)."""
        with zipfile.ZipFile(BytesIO(base64.b64decode(cdr_b64))) as zf:
            nombres = [n for n in zf.namelist() if n.lower().endswith('.xml')]
            raiz = etree.fromstring(zf.read(nombres[0]))
        def texto(local):
            nodo = raiz.xpath('.//*[local-name()="%s"]' % local)
            return (nodo[0].text or '').strip() if nodo else ''
        notas = [(n.text or '').strip() for n in raiz.xpath('.//*[local-name()="Note"]') if n.text]
        return texto('ResponseCode'), texto('Description'), notas

    @staticmethod
    def _ose_codigo_error(respuesta):
        for texto in (respuesta.get('faultcode'), respuesta.get('faultstring')):
            m = re.search(r'(?<!\d)(\d{4})(?!\d)', texto or '')
            if m:
                return m.group(1)
        return False

    def _ose_enviar(self):
        """Envía el XML firmado a la OSE (sendBill) y guarda la respuesta."""
        self.ensure_one()
        from odoo.addons.solse_pe_cpe.models.cpe_core import send_sunat_cpe
        if self.ose_estado in ('aceptado', 'observado'):
            return
        if not self.ose_xml_firmado:
            self._ose_generar()
        empresa = self._ose_empresa()
        servidor = empresa.pe_cpe_server_id
        if not servidor or not servidor.user or not servidor.password:
            raise UserError(_('Falta el servidor OSE (URL, usuario y clave) en la configuración de la empresa.'))
        ruc = empresa.partner_id.doc_number
        nombre = rx.nombre_archivo(ruc, self.name)
        url = (empresa.nuage_ret_ose_url or '').strip() or servidor.url
        cliente = {'ruc': ruc, 'username': servidor.user, 'password': servidor.password, 'url': url}
        documento = {'document_name': nombre, 'type': 'sync',
                     'xml': base64.b64decode(self.ose_xml_firmado)}
        vals = {'ose_fecha_envio': fields.Datetime.now(), 'ose_intentos': (self.ose_intentos or 0) + 1}
        try:
            _zip, ok, respuesta, data = send_sunat_cpe(cliente, documento, SoapClient)
        except Exception as e:  # noqa: BLE001 — se registra y se reintenta
            _logger.warning('Retención %s: fallo al llamar a la OSE: %s', self.name, e)
            vals.update(ose_estado='pendiente', ose_codigo=False,
                        ose_respuesta=_('Sin respuesta de la OSE: %s') % e)
            self.write(vals)
            return
        if ok:
            codigo, descripcion, notas, ilegible = '', '', [], False
            try:
                codigo, descripcion, notas = self._ose_leer_cdr(data)
            except Exception as e:  # noqa: BLE001 — SUNAT ya aceptó: no se pierde el estado
                _logger.warning('Retención %s: el CDR no se pudo interpretar: %s', self.name, e)
                ilegible = True
                notas = [_('El CDR está adjunto pero no se pudo interpretar (%s).') % e]
            try:
                numero = int(codigo)
            except (TypeError, ValueError):
                numero = 0
            # Solo es observación una nota con código SUNAT (4xxx); notas informativas
            # como «Nubefact DEMO» de la OSE de pruebas no cambian el estado.
            observado = numero >= 4000 or any(re.match(r'\s*4\d{3}\b', n or '') for n in notas)
            vals.update({
                'ose_estado': 'observado' if observado else 'aceptado',
                'ose_codigo': codigo or '0',
                'ose_respuesta': descripcion or _('Aceptado'),
                'ose_nota': '\n'.join(notas) or False,
                'ose_cdr': data,
                'ose_cdr_fname': 'R-%s.zip' % nombre,
            })
        else:
            codigo = self._ose_codigo_error(respuesta or {})
            texto = (respuesta or {}).get('faultstring') or _('Sin respuesta válida de la OSE.')
            # 0100-0999: la OSE no pudo responder, se reintenta. 1000 o más: rechazo definitivo
            # (p. ej. 1033 «registrado previamente con otros datos»): reenviar solo agrava.
            definitivo = bool(codigo) and int(codigo) >= 1000
            vals.update({
                'ose_estado': 'rechazado' if definitivo else 'pendiente',
                'ose_codigo': codigo,
                'ose_respuesta': texto,
                'ose_nota': False,
            })
        self.write(vals)
        self.message_post(body=_('OSE: %(estado)s %(codigo)s %(resp)s',
                                 estado=dict(self._fields['ose_estado'].selection).get(vals['ose_estado']),
                                 codigo=vals.get('ose_codigo') or '', resp=vals.get('ose_respuesta') or ''))

    def action_ose_enviar(self):
        enviados = self.filtered(lambda r: r.ose_estado in ('aceptado', 'observado'))
        for rec in self - enviados:
            if rec.state != 'emitido':
                raise UserError(_('Emita el comprobante antes de enviarlo a la OSE.'))
            rec.ose_intentos = 0
            rec._ose_generar()
            rec._ose_enviar()
        return enviados._ose_aviso_ya_enviado() if enviados else True

    def _ose_enviar_seguro(self):
        """Para el cron: nunca levanta; deja el fallo anotado en el comprobante."""
        self.ensure_one()
        try:
            with self.env.cr.savepoint():
                self._ose_enviar()
        except Exception as e:  # noqa: BLE001
            _logger.exception('Retención %s: error al enviar a la OSE', self.name)
            self.write({'ose_intentos': (self.ose_intentos or 0) + 1,
                        'ose_respuesta': str(e)[:250]})
            self.message_post(body=_('Error al enviar a la OSE (intento %(n)s): %(e)s',
                                     n=self.ose_intentos, e=e))

    @api.model
    def _cron_ose_enviar(self):
        pendientes = self.search([
            ('state', '=', 'emitido'),
            ('ose_estado', '=', 'pendiente'),
            ('ose_intentos', '<', MAX_INTENTOS),
            ('company_id.nuage_ret_enviar_ose', '=', True),
        ], order='id', limit=50)
        for rec in pendientes:
            rec._ose_enviar_seguro()
            self.env.cr.commit()  # lo ya enviado a la OSE no debe deshacerse

    # ------------------------------------------------- ganchos del flujo base
    def action_emitir(self):
        res = super().action_emitir()
        if any(r.company_id.nuage_ret_enviar_ose for r in self):
            # Pide al cron que corra enseguida (en otra transacción, tras confirmar la emisión).
            try:
                cron = self.env.ref('nuage_pe_retencion.ir_cron_ose_enviar', raise_if_not_found=False)
                if cron:
                    cron.sudo()._trigger()
            except Exception:  # noqa: BLE001 — no debe bloquear la emisión
                _logger.exception('No se pudo programar el envío inmediato a la OSE')
        return res

    def action_cancelar(self):
        for rec in self:
            if rec.ose_estado in ('aceptado', 'observado'):
                raise UserError(_(
                    'El comprobante %s ya fue aceptado por SUNAT y no se puede cancelar desde aquí: '
                    'requiere un comprobante de reversión.') % rec.name)
        return super().action_cancelar()
