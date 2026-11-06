# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
import calendar
import datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..models import calculo, pdf

MESES = ['ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO', 'JULIO', 'AGOSTO',
         'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE']
TIPOS_FACTURA = ('out_invoice', 'out_refund', 'in_invoice', 'in_refund')
CUENTAS_GESTION = ('6', '7', '8', '9')   # sus saldos no se arrastran de un ejercicio a otro


def _mes_anterior():
    hoy = datetime.date.today()
    fin = hoy.replace(day=1) - datetime.timedelta(days=1)
    return fin.replace(day=1), fin


class LibroImpreso(models.TransientModel):
    _name = 'nuage.libro.impreso'
    _description = 'Libro Diario / Libro Mayor impreso'

    tipo = fields.Selection([('diario', 'Libro Diario (Formato 5.1)'),
                             ('mayor', 'Libro Mayor (Formato 6.1)')], required=True, default='diario')
    company_id = fields.Many2one('res.company', 'Compañía', required=True,
                                 default=lambda self: self.env.company)
    fecha_desde = fields.Date('Desde', required=True, default=lambda self: _mes_anterior()[0])
    fecha_hasta = fields.Date('Hasta', required=True, default=lambda self: _mes_anterior()[1])
    folio_inicial = fields.Integer('Folio inicial', default=1,
                                   help='Número de la primera página (Pag.). Útil si el libro continúa un folio anterior.')
    prefijos_cuentas = fields.Char(
        'Solo cuentas que empiecen con', help='Opcional. Separadas por coma, por ejemplo: 10,12,70')
    solo_con_movimiento = fields.Boolean(
        'Omitir cuentas sin saldo ni movimientos', default=True,
        help='Solo Libro Mayor.')
    mayusculas = fields.Boolean('Imprimir en mayúsculas', default=True)

    # ------------------------------------------------------------------
    @api.constrains('fecha_desde', 'fecha_hasta')
    def _check_fechas(self):
        for rec in self:
            if rec.fecha_desde > rec.fecha_hasta:
                raise UserError(_('La fecha inicial no puede ser posterior a la final.'))

    # ------------------------------------------------------------------
    # Datos
    # ------------------------------------------------------------------
    def _prefijos(self):
        self.ensure_one()
        return tuple(p.strip() for p in (self.prefijos_cuentas or '').split(',') if p.strip())

    def _texto(self, valor):
        """Texto apto para Helvetica (Latin-1/WinAnsi); mayúsculas opcionales."""
        valor = (valor or '').replace('\n', ' ').strip()
        if self.mayusculas:
            valor = valor.upper()
        return valor.encode('cp1252', 'replace').decode('cp1252')

    def _cuentas(self, ids):
        company = self.company_id
        res = {}
        for a in self.env['account.account'].with_company(company).browse(list(ids)):
            res[a.id] = (a.code or '', a.name or '')
        return res

    def _libro_de_diario(self, journal):
        return journal.nuage_libro_impreso or calculo.libro_por_tipo_diario(journal.type)

    def _doc_sustento(self, move, doc_pagos):
        if move.move_type in TIPOS_FACTURA:
            serie = getattr(move, 'solse_pe_serie', '') or ''
            numero = getattr(move, 'solse_pe_numero', '') or ''
            if serie and numero:
                return '%s-%s' % (serie, numero)
            if move.move_type.startswith('out'):
                return move.l10n_latam_document_number or move.name or ''
            return move.ref or ''
        if move.id in doc_pagos:
            return doc_pagos[move.id]
        return move.ref or ''

    def _glosa(self, move, nombre_linea):
        glosa = getattr(move, 'glosa', '') or ''
        if glosa:
            return glosa
        if move.move_type in TIPOS_FACTURA:
            return ' - '.join(x for x in (move.partner_id.name, move.ref) if x) or move.name or ''
        return move.ref or nombre_linea or move.name or ''

    def _docs_de_pagos(self, moves):
        """Número(s) de comprobante que cancela cada pago, para la columna Doc. Sustent."""
        res = {}
        pagos = self.env['account.payment'].search([('move_id', 'in', moves.ids)])
        for p in pagos:
            docs = []
            for campo in ('reconciled_invoice_ids', 'reconciled_bill_ids'):
                if campo in p._fields:
                    for f in p[campo]:
                        serie = getattr(f, 'solse_pe_serie', '') or ''
                        numero = getattr(f, 'solse_pe_numero', '') or ''
                        docs.append('%s-%s' % (serie, numero) if serie and numero else (f.ref or f.name or ''))
            docs = [d for d in docs if d]
            if docs:
                res[p.move_id.id] = docs[0]
        return res

    def _lineas(self, desde, hasta):
        """Líneas publicadas del período, con cuenta, asiento y diario ya resueltos."""
        company = self.company_id
        Line = self.env['account.move.line'].with_company(company)
        # Las líneas de sección o nota de las facturas no tienen cuenta: no son apuntes contables.
        dominio = [('company_id', '=', company.id), ('parent_state', '=', 'posted'),
                   ('account_id', '!=', False),
                   ('date', '>=', desde), ('date', '<=', hasta)]
        lineas = Line.search_read(dominio, ['move_id', 'account_id', 'debit', 'credit', 'name'], order='id')
        if not lineas:
            return [], {}
        lineas = [l for l in lineas if l['account_id']]
        cuentas = self._cuentas({l['account_id'][0] for l in lineas})
        return lineas, cuentas

    def _asientos(self):
        """Asientos numerados (libro, vou) del período, con sus líneas ordenadas."""
        self.ensure_one()
        lineas, cuentas = self._lineas(self.fecha_desde, self.fecha_hasta)
        if not lineas:
            return []
        Move = self.env['account.move'].with_company(self.company_id)
        moves = Move.browse(sorted({l['move_id'][0] for l in lineas}))
        doc_pagos = self._docs_de_pagos(moves)
        por_move = {}
        for l in lineas:
            por_move.setdefault(l['move_id'][0], []).append(l)
        asientos = []
        for m in moves:
            ls = por_move.get(m.id, [])
            asientos.append({
                'id': m.id,
                'libro': self._libro_de_diario(m.journal_id),
                'fecha': m.date,
                'cuo': self._texto(m.name or str(m.id)),
                'doc': self._texto(self._doc_sustento(m, doc_pagos)),
                'glosa': self._texto(self._glosa(m, ls[0]['name'] if ls else '')),
                'lineas': [{
                    'seq': l['id'], 'cuenta': cuentas[l['account_id'][0]][0],
                    'denominacion': self._texto(cuentas[l['account_id'][0]][1]),
                    'debe': calculo.redondear(l['debit']), 'haber': calculo.redondear(l['credit']),
                } for l in ls if abs(l['debit']) >= calculo.TOL or abs(l['credit']) >= calculo.TOL],
            })
        # Se numera con todos los asientos; el filtro por cuentas solo recorta lo impreso,
        # así el correlativo (Vou) coincide con el del libro completo.
        asientos = calculo.numerar_asientos(asientos)
        prefijos = self._prefijos()
        for a in asientos:
            if prefijos:
                a['lineas'] = [l for l in a['lineas'] if l['cuenta'].startswith(prefijos)]
            a['lineas'] = calculo.ordenar_lineas_asiento(a['lineas'])
        return [a for a in asientos if a['lineas']]

    def _saldos_anteriores(self):
        """Saldo (debe - haber) al inicio del período por cuenta.

        Cuentas de balance (1-5): todo lo anterior. Cuentas de gestión (6-9): solo
        desde el 1 de enero del año de la fecha inicial.
        """
        company = self.company_id
        Line = self.env['account.move.line'].with_company(company)
        base = [('company_id', '=', company.id), ('parent_state', '=', 'posted'), ('account_id', '!=', False)]
        inicio_anio = self.fecha_desde.replace(month=1, day=1)
        acum = {}
        for dom, es_gestion in (
                (base + [('date', '<', self.fecha_desde)], False),
                (base + [('date', '>=', inicio_anio), ('date', '<', self.fecha_desde)], True)):
            grupos = Line._read_group(dom, groupby=['account_id'], aggregates=['balance:sum'])
            ids = [g[0].id for g in grupos]
            codigos = self._cuentas(ids)
            for cuenta, saldo in grupos:
                codigo = codigos[cuenta.id][0]
                if codigo.startswith(CUENTAS_GESTION) == es_gestion:
                    acum[cuenta.id] = (codigo, codigos[cuenta.id][1], saldo)
        return acum

    # ------------------------------------------------------------------
    # Salida
    # ------------------------------------------------------------------
    def _cabecera(self):
        company = self.company_id
        partner = company.partner_id
        if (self.fecha_desde.day == 1 and self.fecha_desde.year == self.fecha_hasta.year
                and self.fecha_desde.month == self.fecha_hasta.month
                and self.fecha_hasta.day == calendar.monthrange(self.fecha_hasta.year, self.fecha_hasta.month)[1]):
            periodo = '%s %s' % (MESES[self.fecha_desde.month - 1], self.fecha_desde.year)
        else:
            periodo = 'DEL %s AL %s' % (self.fecha_desde.strftime('%d/%m/%Y'), self.fecha_hasta.strftime('%d/%m/%Y'))
        direccion = ' - '.join(x for x in (partner.street, partner.city) if x)
        vat = partner.vat or company.vat or ''
        if vat.startswith('PE'):
            vat = vat[2:]
        return {
            'empresa': self._texto(partner.name or company.name),
            'periodo': periodo,
            'direccion': self._texto(direccion),
            'ruc': vat,
        }

    def _generar_pdf(self):
        self.ensure_one()
        cab = self._cabecera()
        if self.tipo == 'diario':
            asientos = self._asientos()
            if not asientos:
                raise UserError(_('No hay asientos publicados en el período indicado.'))
            return pdf.render_diario(cab, calculo.paginar_diario(asientos), self.folio_inicial or 1)
        asientos = self._asientos()
        anteriores = self._saldos_anteriores()
        prefijos = self._prefijos()
        cuentas = {}
        for a in asientos:
            for l in a['lineas']:
                cu = cuentas.setdefault(l['cuenta'], {
                    'cuenta': l['cuenta'], 'denominacion': l['denominacion'],
                    'saldo_anterior': 0.0, 'movs': []})
                cu['movs'].append({
                    'libro': a['libro'], 'vou': a['vou'], 'cuo': a['cuo'], 'fecha': a['fecha'],
                    'doc': a['doc'], 'glosa': a['glosa'], 'debe': l['debe'], 'haber': l['haber']})
        for codigo, nombre, saldo in anteriores.values():
            if prefijos and not codigo.startswith(prefijos):
                continue
            cu = cuentas.setdefault(codigo, {'cuenta': codigo, 'denominacion': self._texto(nombre),
                                             'saldo_anterior': 0.0, 'movs': []})
            cu['saldo_anterior'] = calculo.redondear(saldo)
        if not cuentas:
            raise UserError(_('No hay movimientos ni saldos en el período indicado.'))
        lista, totales = calculo.armar_mayor(list(cuentas.values()), self.solo_con_movimiento)
        if not lista:
            raise UserError(_('No hay cuentas con saldo ni movimientos en el período indicado.'))
        return pdf.render_mayor(cab, calculo.paginar_mayor(lista, totales), self.fecha_desde,
                                self.folio_inicial or 1)

    def action_imprimir(self):
        self.ensure_one()
        contenido = self._generar_pdf()
        nombre = 'Libro_%s_%s_%s.pdf' % (
            'Diario_5.1' if self.tipo == 'diario' else 'Mayor_6.1',
            self.fecha_desde.strftime('%Y%m%d'), self.fecha_hasta.strftime('%Y%m%d'))
        adjunto = self.env['ir.attachment'].create({
            'name': nombre, 'raw': contenido, 'mimetype': 'application/pdf'})
        return {'type': 'ir.actions.act_url', 'url': '/web/content/%s?download=false' % adjunto.id,
                'target': 'new'}
