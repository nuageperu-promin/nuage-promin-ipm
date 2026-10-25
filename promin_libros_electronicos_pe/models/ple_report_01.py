# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
import base64
import datetime
import logging

from odoo import fields, models, _
from odoo.exceptions import UserError

from odoo.addons.solse_pe_ple_pro.models.ple_report import (
    fill_name_data,
    get_last_day,
)
from . import ple_01_format as fmt

_logging = logging.getLogger(__name__)

TIPOS_CON_COMPROBANTE = ('out_invoice', 'out_refund', 'in_invoice', 'in_refund')

CABECERAS_11 = [
    'Periodo',
    'Código Único de la Operación (CUO)',
    'Número correlativo del asiento contable',
    'Código de la cuenta contable del efectivo',
    'Código de la Unidad de Operación / Unidad de Negocio',
    'Código del Centro de Costos / Utilidades / Inversión',
    'Tipo de Moneda de origen',
    'Tipo de Comprobante de Pago o Documento',
    'Número de serie del comprobante de pago o documento',
    'Número del comprobante de pago o documento',
    'Fecha contable',
    'Fecha de vencimiento',
    'Fecha de la operación o emisión',
    'Glosa o descripción de la naturaleza de la operación',
    'Glosa referencial',
    'Movimientos del Debe',
    'Movimientos del Haber',
    'Dato estructurado',
    'Indica el estado de la operación',
]

CABECERAS_12 = [
    'Periodo',
    'Código Único de la Operación (CUO)',
    'Número correlativo del asiento contable',
    'Código de la entidad financiera (Tabla 3)',
    'Código de la cuenta bancaria del contribuyente',
    'Fecha de la operación',
    'Medio de pago utilizado (Tabla 1)',
    'Descripción de la operación bancaria',
    'Tipo de documento de identidad del girador o beneficiario',
    'Número de documento de identidad del girador o beneficiario',
    'Apellidos y nombres, denominación o razón social',
    'Número de transacción bancaria o control interno',
    'Parte deudora de saldos y movimientos',
    'Parte acreedora de saldos y movimientos',
    'Indica el estado de la operación',
]


def _fecha(valor):
    return valor.strftime('%d/%m/%Y') if valor else ''


class PLEReport01(models.Model):
    _name = 'ple.report.01'
    _description = 'PLE 01 - Estructura del Libro Caja y Bancos'
    _inherit = 'ple.report.templ'

    year = fields.Integer(required=True)
    month = fields.Selection(selection_add=[], required=True)

    line_ids = fields.Many2many(
        comodel_name='account.move.line', string='Movimientos', readonly=True)

    ple_txt_01 = fields.Text(string='Contenido del TXT 1.1')
    ple_txt_01_binary = fields.Binary(string='TXT 1.1', readonly=True)
    ple_txt_01_filename = fields.Char(string='Nombre del TXT 1.1')
    ple_xls_01_binary = fields.Binary(string='Excel 1.1', readonly=True)
    ple_xls_01_filename = fields.Char(string='Nombre del Excel 1.1')
    ple_txt_02 = fields.Text(string='Contenido del TXT 1.2')
    ple_txt_02_binary = fields.Binary(string='TXT 1.2', readonly=True)
    ple_txt_02_filename = fields.Char(string='Nombre del TXT 1.2')
    ple_xls_02_binary = fields.Binary(string='Excel 1.2', readonly=True)
    ple_xls_02_filename = fields.Char(string='Nombre del Excel 1.2')

    # ------------------------------------------------------------------
    # Nombre de archivo y selección de líneas
    # ------------------------------------------------------------------

    def get_default_filename(self, ple_id='010100', tiene_datos=False):
        # LE + RUC + AAAA + MM + 00 + LLLLLL + 00 + O I M G (hoja «Reglas de
        # nombres de libros»): el libro 1 es mensual, lleva '00' en día y en
        # oportunidad. El indicador de moneda queda en '1' (soles): los
        # importes de 1.1 y 1.2 se informan en moneda nacional.
        name = super().get_default_filename()
        name_dict = {
            'month': str(self.month).rjust(2, '0'),
            'ple_id': ple_id,
        }
        if not tiene_datos:
            name_dict['contenido'] = '0'
        fill_name_data(name_dict)
        return name % name_dict

    def update_report(self):
        res = super().update_report()
        inicio = datetime.date(self.year, int(self.month), 1)
        fin = get_last_day(inicio)
        domain = [
            ('company_id', '=', self.company_id.id),
            ('move_id.state', '=', 'posted'),
            ('display_type', 'not in', ['line_section', 'line_subsection', 'line_note']),
            ('date', '>=', str(inicio)),
            ('date', '<=', str(fin)),
            '|',
            ('account_id.is_cash_account', '=', True),
            ('account_id.is_bank_account', '=', True),
        ]
        self.line_ids = self.env['account.move.line'].search(
            domain, order='date asc, move_id asc, id asc')
        return res

    # ------------------------------------------------------------------
    # Datos de apoyo
    # ------------------------------------------------------------------

    def _mapa_pagos(self, lineas_banco):
        """{account.move.id: account.payment} para las líneas de banco.

        Primero por el asiento del pago; para asientos manuales, vía la
        conciliación de la línea. Una consulta por bloque, sin N+1.
        """
        mapa = {}
        if not lineas_banco:
            return mapa
        pagos = self.env['account.payment'].sudo().search(
            [('move_id', 'in', lineas_banco.mapped('move_id').ids)])
        for pago in pagos:
            mapa[pago.move_id.id] = pago
        for linea in lineas_banco:
            if linea.move_id.id in mapa:
                continue
            pago = (
                linea.matched_debit_ids.mapped('debit_move_id.payment_id')[:1]
                or linea.matched_credit_ids.mapped('credit_move_id.payment_id')[:1]
            )
            if pago:
                mapa[linea.move_id.id] = pago[0]
        return mapa

    def _mapa_diarios_banco(self):
        """{account.account.id: account.journal}: diario de banco de cada cuenta.

        La cuenta bancaria del contribuyente (C5) es la del diario dueño de la
        cuenta contable, no la del diario del asiento: un ajuste hecho en un
        diario varios sobre la cuenta 104 seguiría siendo del mismo banco.
        Si dos diarios comparten cuenta contable se prefiere el que tiene
        cuenta bancaria configurada.
        """
        diarios = self.env['account.journal'].sudo().search([
            ('company_id', '=', self.company_id.id),
            ('type', '=', 'bank'),
        ])
        mapa = {}
        for diario in diarios:
            cuenta = diario.default_account_id
            if not cuenta:
                continue
            previo = mapa.get(cuenta.id)
            if previo is None or (not previo.bank_account_id and diario.bank_account_id):
                mapa[cuenta.id] = diario
        return mapa

    def _validar_diarios_banco(self, diarios):
        """Falla antes de generar si un diario de banco no tiene número de cuenta.

        C5 es llave única y se declara a SUNAT como la cuenta del contribuyente:
        rellenarlo con el nombre del diario (como hace el 5.1 para los
        eximidos) produce un archivo que pasa el validador y declara una cuenta
        que no existe.
        """
        sin_cuenta = sorted({
            d.display_name for d in diarios
            if not (d.bank_account_id and (d.bank_account_id.acc_number or '').strip())
        })
        if sin_cuenta:
            raise UserError(_(
                "No se puede generar la estructura 1.2: los siguientes diarios de "
                "banco no tienen cuenta bancaria con número configurado.\n\n"
                "%(lista)s\n\n"
                "Configúrela en Contabilidad → Configuración → Diarios → "
                "«Número de cuenta» y asocie el banco con su código SUNAT "
                "(Tabla 3) en Contabilidad → Configuración → Bancos."
            ) % {'lista': '\n'.join('  • ' + nombre for nombre in sin_cuenta)})

    def _datos_comprobante(self, move):
        """(tipo, serie, número, fecha de vencimiento) del asiento, para 1.1."""
        tipo = move.pe_invoice_code or '00'
        if move.move_type in TIPOS_CON_COMPROBANTE:
            serie = move.solse_pe_serie or ''
            numero = move.solse_pe_numero or move.name or str(move.id)
            vencimiento = _fecha(move.invoice_date_due)
        else:
            # Asientos puros y pagos: sin comprobante SUNAT; el nombre del
            # asiento hace de número y el vencimiento no aplica.
            serie = ''
            numero = move.name or str(move.id)
            vencimiento = ''
        return tipo, serie, numero, vencimiento

    # ------------------------------------------------------------------
    # Generación
    # ------------------------------------------------------------------

    def generate_report(self):
        # Los campos company-dependent de Odoo 19 (`account.account.code`) se
        # leen según la compañía ACTIVA: todo el método trabaja anclado a la
        # compañía del libro, igual que el 5.1.
        self = self.with_company(self.company_id)
        res = super().generate_report()
        lineas = self.line_ids.sudo()
        fecha_inicio = datetime.date(self.year, int(self.month), 1)

        # CUO y correlativo salen del mismo mapa que usan el Diario y el Mayor:
        # SUNAT exige que el CUO del 1.2 sea el mismo del Libro Diario.
        mapa_correlativos = self._construir_mapa_correlativos(lineas)
        anteriores = [l.move_id.id for l in lineas if l.move_id.date < fecha_inicio]
        ya_declarados = self._construir_cache_moves_declarados(anteriores)

        lineas_efectivo = lineas.filtered(lambda l: l.account_id.is_cash_account)
        lineas_banco = lineas.filtered(lambda l: l.account_id.is_bank_account)

        mapa_pagos = self._mapa_pagos(lineas_banco)
        mapa_diarios = self._mapa_diarios_banco()
        diarios_usados = {
            l.id: (mapa_diarios.get(l.account_id.id) or l.move_id.journal_id)
            for l in lineas_banco
        }
        if lineas_banco:
            unicos = {d.id: d for d in diarios_usados.values()}
            self._validar_diarios_banco(list(unicos.values()))

        registros_11 = []
        for linea in lineas_efectivo:
            registro = self._registro_11(
                linea, mapa_correlativos, fecha_inicio, ya_declarados)
            if registro:
                registros_11.append(registro)

        registros_12 = []
        for linea in lineas_banco:
            registro = self._registro_12(
                linea, mapa_correlativos, fecha_inicio, ya_declarados,
                mapa_pagos, diarios_usados[linea.id])
            if registro:
                registros_12.append(registro)

        filas_11 = [fmt.linea_11(r) for r in fmt.consolidar_11(registros_11)]
        filas_12 = [fmt.linea_12(r) for r in fmt.consolidar_12(registros_12)]

        valores = {}
        valores.update(self._archivos(
            '010100', '1.1', '01', filas_11, CABECERAS_11))
        valores.update(self._archivos(
            '010200', '1.2', '02', filas_12, CABECERAS_12))
        valores['date_generated'] = str(fields.Datetime.now())
        self.write(valores)
        return res

    def _archivos(self, ple_id, etiqueta, sufijo, filas, cabeceras):
        """Valores de los campos TXT/Excel de una estructura (o todo en False)."""
        vacio = {
            'ple_txt_%s' % sufijo: False,
            'ple_txt_%s_binary' % sufijo: False,
            'ple_txt_%s_filename' % sufijo: False,
            'ple_xls_%s_binary' % sufijo: False,
            'ple_xls_%s_filename' % sufijo: False,
        }
        if not filas:
            return vacio
        nombre = self.get_default_filename(ple_id=ple_id, tiene_datos=True)
        texto = '\r\n'.join(filas + [''])
        xlsx = self._generate_xlsx_base64_bytes(
            texto, nombre[2:], headers=cabeceras)
        return {
            'ple_txt_%s' % sufijo: texto,
            'ple_txt_%s_binary' % sufijo: base64.b64encode(self._codificar_txt(texto)),
            'ple_txt_%s_filename' % sufijo: nombre + '.txt',
            'ple_xls_%s_binary' % sufijo: xlsx.encode(),
            'ple_xls_%s_filename' % sufijo: nombre + '.xlsx',
        }

    def _registro_11(self, linea, mapa_correlativos, fecha_inicio, ya_declarados):
        """Registro de la estructura 1.1 para una línea de cuenta de efectivo."""
        try:
            move = linea.move_id
            cuo, correlativo = mapa_correlativos[move.id]
            tipo, serie, numero, vencimiento = self._datos_comprobante(move)
            moneda = (linea.currency_id or move.currency_id
                      or self.company_id.currency_id).name or 'PEN'
            fecha_operacion = move.date
            if move.move_type in TIPOS_CON_COMPROBANTE and move.invoice_date:
                fecha_operacion = move.invoice_date
            glosa = self._formato_glosa(
                getattr(move, 'glosa', None) or linea.name or move.ref or move.name, 200
            ) or 'MOVIMIENTO DE EFECTIVO'
            return {
                'periodo': move.date.strftime('%Y%m00'),
                'cuo': cuo,
                'correlativo': correlativo,
                'cuenta': linea.account_id.code or '',
                'moneda': moneda,
                'tipo_cp': tipo,
                'serie': serie,
                'numero': numero,
                'f_contable': _fecha(move.date),
                'f_venc': vencimiento,
                'f_op': _fecha(fecha_operacion),
                'glosa': glosa,
                'debe': fmt.a_centimos(linea.debit),
                'haber': fmt.a_centimos(linea.credit),
                'estado': self._obtener_estado_ple(move, fecha_inicio, ya_declarados),
            }
        except Exception:
            # Una línea que falla NO debe desaparecer sin rastro: el libro
            # saldría incompleto y nadie lo notaría hasta el validador.
            _logging.exception(
                'PLE 1.1: la línea %s (asiento %s) no se pudo formatear y NO '
                'entra al libro.', linea.id, linea.move_id.name)
            return None

    def _registro_12(self, linea, mapa_correlativos, fecha_inicio, ya_declarados,
                     mapa_pagos, diario):
        """Registro de la estructura 1.2 para una línea de cuenta bancaria."""
        try:
            move = linea.move_id
            cuo, correlativo = mapa_correlativos[move.id]
            pago = mapa_pagos.get(move.id)

            banco = ''
            if diario.bank_account_id and diario.bank_account_id.bank_id:
                banco = diario.bank_account_id.bank_id.l10n_pe_bank_code or ''
            if not banco:
                _logging.warning(
                    'PLE 1.2: el banco del diario «%s» no tiene código SUNAT '
                    '(Tabla 3); se informa 99 (otros).', diario.display_name)

            partner = (pago.partner_id if pago else False) or linea.partner_id \
                or move.partner_id
            tipo_doc, nro_doc = '', ''
            if partner:
                tipo_doc = partner.l10n_latam_identification_type_id.l10n_pe_vat_code or ''
                nro_doc = partner.vat or ''

            transaccion = (
                move.transaction_number
                or (pago.transaction_number if pago else '')
                or ''
            )
            if not transaccion:
                # Último recurso: el nombre del asiento, recortado por la cola
                # porque ahí está la parte que lo hace único.
                transaccion = fmt.sanear_alfanumerico(
                    move.name or str(move.id), 20, desde_cola=True)

            return {
                'periodo': move.date.strftime('%Y%m00'),
                'cuo': cuo,
                'correlativo': correlativo,
                'banco': banco,
                'cuenta_bancaria': (diario.bank_account_id.acc_number or '').strip(),
                'f_op': _fecha(move.date),
                'medio_pago': (pago.l10n_pe_payment_method_code if pago else '') or '',
                'descripcion': getattr(move, 'glosa', None) or move.ref or linea.name or '',
                'tipo_doc': tipo_doc,
                'nro_doc': nro_doc,
                'razon_social': (partner.name if partner else '') or 'varios',
                'nro_transaccion': transaccion,
                'debe': fmt.a_centimos(linea.debit),
                'haber': fmt.a_centimos(linea.credit),
                'estado': self._obtener_estado_ple(move, fecha_inicio, ya_declarados),
            }
        except Exception:
            _logging.exception(
                'PLE 1.2: la línea %s (asiento %s) no se pudo formatear y NO '
                'entra al libro.', linea.id, linea.move_id.name)
            return None
