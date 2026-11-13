# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
from odoo import _, api, fields, models


class ObligacionCuota(models.Model):
    _name = 'promin.obligacion.cuota'
    _description = 'Cuota de obligación financiera'
    _order = 'fecha, numero, id'

    obligacion_id = fields.Many2one('promin.obligacion', string='Obligación', required=True,
                                    ondelete='cascade', index=True)
    company_id = fields.Many2one(related='obligacion_id.company_id', store=True, string='Compañía')
    banco_id = fields.Many2one(related='obligacion_id.banco_id', store=True, string='Banco / entidad')
    tipo = fields.Selection(related='obligacion_id.tipo', store=True, string='Tipo')
    currency_id = fields.Many2one(related='obligacion_id.currency_id', store=True, string='Moneda')
    obligacion_state = fields.Selection(related='obligacion_id.state', store=True, string='Estado de la obligación')
    numero = fields.Integer(string='N°')
    fecha = fields.Date(string='Vencimiento', required=True)
    capital = fields.Monetary(string='Capital', currency_field='currency_id')
    interes = fields.Monetary(string='Interés', currency_field='currency_id')
    comision = fields.Monetary(string='Comisión', currency_field='currency_id')
    itf = fields.Monetary(string='ITF / portes / otros', currency_field='currency_id')
    total = fields.Monetary(string='Total cuota', currency_field='currency_id',
                            compute='_compute_total', store=True)
    estado = fields.Selection([('pendiente', 'Pendiente'), ('pagada', 'Pagada')],
                              string='Estado', default='pendiente', required=True)
    fecha_pago = fields.Date(string='Fecha de pago', readonly=True, copy=False)
    capital_pagado = fields.Monetary(string='Capital pagado', currency_field='currency_id', readonly=True, copy=False)
    interes_pagado = fields.Monetary(string='Interés pagado', currency_field='currency_id', readonly=True, copy=False)
    comision_pagada = fields.Monetary(string='Comisión pagada', currency_field='currency_id',
                                      readonly=True, copy=False)
    itf_pagado = fields.Monetary(string='ITF / portes pagados', currency_field='currency_id',
                                 readonly=True, copy=False)
    move_id = fields.Many2one('account.move', string='Asiento del pago', readonly=True, copy=False)
    alerta_enviada = fields.Boolean(string='Alerta enviada', default=False, copy=False)
    dias_para_vencer = fields.Integer(string='Días para vencer', compute='_compute_dias')

    @api.depends('numero', 'obligacion_id.nro_operacion')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s - Cuota %s' % (rec.obligacion_id.nro_operacion or '', rec.numero)

    @api.depends('capital', 'interes', 'comision', 'itf')
    def _compute_total(self):
        for rec in self:
            rec.total = rec.capital + rec.interes + rec.comision + rec.itf

    def _compute_dias(self):
        hoy = fields.Date.context_today(self)
        for rec in self:
            rec.dias_para_vencer = (rec.fecha - hoy).days if rec.fecha and rec.estado == 'pendiente' else 0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('numero') and vals.get('obligacion_id'):
                ultimo = self.search([('obligacion_id', '=', vals['obligacion_id'])], order='numero desc', limit=1)
                vals['numero'] = (ultimo.numero or 0) + 1
        return super().create(vals_list)

    def write(self, vals):
        if 'fecha' in vals:
            vals = dict(vals, alerta_enviada=False)
        return super().write(vals)

    def action_pagar(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Registrar pago de cuota'),
            'res_model': 'promin.obligacion.pago.wizard', 'view_mode': 'form', 'target': 'new',
            'context': {'default_cuota_id': self.id},
        }
