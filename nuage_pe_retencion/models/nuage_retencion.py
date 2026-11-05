# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .calculo import redondear, retenido_en_soles

# Constante para el bloqueo de numeración (pg_advisory_xact_lock con dos enteros)
LOCK_NUMERACION = 18520


class NuageRetencion(models.Model):
    _name = 'nuage.retencion'
    _description = 'Comprobante de retención (IGV)'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    name = fields.Char('Número', default='/', copy=False, readonly=True, index=True)
    company_id = fields.Many2one(
        'res.company', 'Compañía', required=True, index=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', store=True, string='Moneda')
    partner_id = fields.Many2one('res.partner', 'Proveedor', required=True, index=True)
    partner_vat = fields.Char('RUC', related='partner_id.vat')
    date = fields.Date('Fecha de emisión', required=True, default=fields.Date.context_today)
    serie = fields.Char('Serie', copy=False, readonly=True)
    correlativo = fields.Integer('Correlativo', copy=False, readonly=True)
    tasa = fields.Float('Tasa (%)', digits=(5, 2), required=True, default=3.0)
    payment_id = fields.Many2one(
        'account.payment', 'Pago', readonly=True, index=True, copy=False, ondelete='set null')
    payment_state = fields.Selection(related='payment_id.state', string='Estado del pago')
    state = fields.Selection([
        ('borrador', 'Borrador'),
        ('emitido', 'Emitido'),
        ('cancelado', 'Cancelado'),
    ], string='Estado', default='borrador', required=True, tracking=True, copy=False)
    line_ids = fields.One2many('nuage.retencion.line', 'retencion_id', 'Comprobantes de pago')
    importe_pago = fields.Monetary(
        'Importe de pago sin retención', currency_field='currency_id',
        compute='_compute_totales', store=True)
    importe_retenido = fields.Monetary(
        'Importe retenido', currency_field='currency_id',
        compute='_compute_totales', store=True)
    importe_neto = fields.Monetary(
        'Importe total a pagar', currency_field='currency_id',
        compute='_compute_totales', store=True)
    observaciones = fields.Text('Observaciones')

    @api.depends('line_ids.importe_pago', 'line_ids.tipo_cambio',
                 'line_ids.importe_retenido', 'line_ids.importe_neto')
    def _compute_totales(self):
        for rec in self:
            rec.importe_pago = sum(
                redondear((l.importe_pago or 0.0) * (l.tipo_cambio or 1.0)) for l in rec.line_ids)
            rec.importe_retenido = sum(rec.line_ids.mapped('importe_retenido'))
            rec.importe_neto = sum(rec.line_ids.mapped('importe_neto'))

    @api.constrains('company_id', 'serie', 'correlativo')
    def _check_numero_unico(self):
        for rec in self.filtered('correlativo'):
            repetidos = self.search_count([
                ('id', '!=', rec.id),
                ('company_id', '=', rec.company_id.id),
                ('serie', '=', rec.serie),
                ('correlativo', '=', rec.correlativo),
            ])
            if repetidos:
                raise ValidationError(_('El número %s ya existe para esta compañía.') % rec.name)

    def action_emitir(self):
        for rec in self:
            if rec.state != 'borrador':
                continue
            if not rec.line_ids:
                raise UserError(_('El comprobante no tiene líneas.'))
            company = rec.company_id
            if not company.nuage_ret_serie:
                raise UserError(_(
                    'Configure la serie del comprobante de retención en la compañía '
                    '(pestaña «Retenciones»).'))
            # Un bloqueo por compañía evita números repetidos si dos usuarios emiten a la vez.
            self.env.cr.execute('SELECT pg_advisory_xact_lock(%s, %s)', (LOCK_NUMERACION, company.id))
            self.env.cr.execute(
                'SELECT COALESCE(MAX(correlativo), 0) FROM nuage_retencion '
                'WHERE company_id = %s AND serie = %s', (company.id, company.nuage_ret_serie))
            ultimo = self.env.cr.fetchone()[0]
            siguiente = max(ultimo + 1, company.nuage_ret_correlativo_inicio or 1)
            rec.write({
                'serie': company.nuage_ret_serie,
                'correlativo': siguiente,
                'name': '%s-%08d' % (company.nuage_ret_serie, siguiente),
                'state': 'emitido',
            })
        return True

    def action_cancelar(self):
        self.write({'state': 'cancelado'})
        return True

    def unlink(self):
        if any(rec.state != 'borrador' for rec in self):
            raise UserError(_('Solo se pueden eliminar comprobantes en borrador. Cancele el comprobante.'))
        return super().unlink()


class NuageRetencionLine(models.Model):
    _name = 'nuage.retencion.line'
    _description = 'Línea del comprobante de retención'
    _order = 'retencion_id, id'

    retencion_id = fields.Many2one(
        'nuage.retencion', 'Comprobante', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(
        'res.company', related='retencion_id.company_id', store=True, index=True)
    currency_id = fields.Many2one('res.currency', related='retencion_id.currency_id', store=True)
    partner_id = fields.Many2one(
        'res.partner', related='retencion_id.partner_id', store=True, string='Proveedor', index=True)
    state = fields.Selection(related='retencion_id.state', store=True, string='Estado')
    move_id = fields.Many2one(
        'account.move', 'Factura', required=True, index=True,
        domain=[('move_type', '=', 'in_invoice')])
    numero_doc = fields.Char(
        'Documento', related='move_id.l10n_latam_document_number', store=True)
    fecha_emision = fields.Date('Fecha de emisión', related='move_id.invoice_date', store=True)
    fecha_pago = fields.Date('Fecha de pago', required=True, default=fields.Date.context_today)
    nro_pago = fields.Integer('Nro. de pago', default=1)
    moneda_origen_id = fields.Many2one(
        'res.currency', 'Moneda origen', compute='_compute_moneda_tc', store=True, readonly=False)
    tipo_cambio = fields.Float(
        'Tipo de cambio', digits=(12, 6), compute='_compute_moneda_tc', store=True, readonly=False,
        help='Soles por unidad de la moneda origen, a la fecha de pago.')
    importe_operacion = fields.Monetary(
        'Importe operación/origen', currency_field='moneda_origen_id',
        compute='_compute_importe_operacion', store=True, readonly=False)
    importe_pago = fields.Monetary(
        'Importe de pago sin retención', currency_field='moneda_origen_id')
    importe_pago_pen = fields.Monetary(
        'Importe de pago sin retención S/', currency_field='currency_id',
        compute='_compute_retenido', store=True)
    importe_retenido = fields.Monetary(
        'Importe retenido S/', currency_field='currency_id',
        compute='_compute_retenido', store=True, readonly=False)
    importe_neto = fields.Monetary(
        'Importe total a pagar S/', currency_field='currency_id',
        compute='_compute_retenido', store=True, readonly=False)

    @api.depends('move_id', 'fecha_pago')
    def _compute_moneda_tc(self):
        for line in self:
            move = line.move_id
            line.moneda_origen_id = move.currency_id if move else line.currency_id
            empresa = line.retencion_id.company_id
            if move and empresa and move.currency_id != empresa.currency_id:
                line.tipo_cambio = move.currency_id._get_conversion_rate(
                    move.currency_id, empresa.currency_id, empresa, line.fecha_pago)
            else:
                line.tipo_cambio = 1.0

    @api.depends('move_id')
    def _compute_importe_operacion(self):
        for line in self:
            line.importe_operacion = line.move_id.amount_total if line.move_id else 0.0

    @api.depends('importe_pago', 'tipo_cambio', 'retencion_id.tasa')
    def _compute_retenido(self):
        for line in self:
            tasa = line.retencion_id.tasa or 0.0
            tc = line.tipo_cambio or 1.0
            pago_pen = redondear((line.importe_pago or 0.0) * tc)
            line.importe_pago_pen = pago_pen
            line.importe_retenido = retenido_en_soles(line.importe_pago or 0.0, tc, tasa)
            line.importe_neto = pago_pen - line.importe_retenido
