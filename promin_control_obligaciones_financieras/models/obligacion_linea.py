# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
from odoo import api, fields, models


class ObligacionLinea(models.Model):
    _name = 'promin.obligacion.linea'
    _description = 'Línea de crédito'
    _order = 'banco_id, name'

    name = fields.Char(string='Línea / producto', required=True,
                       help='Ej.: Capital de trabajo, Importación, Carta fianza, Descuento de facturas.')
    company_id = fields.Many2one('res.company', string='Compañía', required=True,
                                 default=lambda self: self.env.company)
    banco_id = fields.Many2one('res.partner', string='Banco / entidad', required=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', required=True,
                                  default=lambda self: self.env.company.currency_id)
    monto_aprobado = fields.Monetary(string='Línea aprobada', currency_field='currency_id')
    utilizacion_maxima = fields.Monetary(
        string='Utilización máxima', currency_field='currency_id',
        help='Tope compartido cuando la línea es múltiple.')
    grupo_multiple = fields.Char(
        string='Línea múltiple',
        help='Mismo texto en las líneas del mismo banco que comparten un tope (ej.: L. MULTIPLE X 300 MIL).')
    plazo_dias = fields.Integer(string='Plazo máximo (días)')
    fecha_vencimiento = fields.Date(string='Vencimiento de la línea')
    active = fields.Boolean(default=True)
    obligacion_ids = fields.One2many('promin.obligacion', 'linea_id', string='Obligaciones')
    utilizado = fields.Monetary(string='Utilizado', currency_field='currency_id', compute='_compute_utilizado')
    disponible = fields.Monetary(string='Disponible', currency_field='currency_id', compute='_compute_utilizado')
    utilizado_grupo = fields.Monetary(
        string='Utilizado del grupo', currency_field='currency_id', compute='_compute_utilizado')
    disponible_grupo = fields.Monetary(
        string='Disponible del grupo', currency_field='currency_id', compute='_compute_utilizado')

    @api.depends('obligacion_ids.saldo_capital', 'obligacion_ids.state', 'monto_aprobado',
                 'utilizacion_maxima', 'grupo_multiple', 'banco_id')
    def _compute_utilizado(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.utilizado = rec._utilizado_propio(today)
            rec.disponible = rec.monto_aprobado - rec.utilizado
            if rec.grupo_multiple and rec.id:
                grupo = self.search([
                    ('company_id', '=', rec.company_id.id), ('banco_id', '=', rec.banco_id.id),
                    ('grupo_multiple', '=', rec.grupo_multiple)])
                total = 0.0
                for lin in grupo:
                    total += lin.currency_id._convert(
                        lin._utilizado_propio(today), rec.currency_id, rec.company_id, today)
                rec.utilizado_grupo = total
                rec.disponible_grupo = rec.utilizacion_maxima - total
            else:
                rec.utilizado_grupo = 0.0
                rec.disponible_grupo = 0.0

    def _utilizado_propio(self, today):
        self.ensure_one()
        total = 0.0
        for obl in self.obligacion_ids.filtered(lambda o: o.state == 'vigente'):
            total += obl.currency_id._convert(obl.saldo_capital, self.currency_id, self.company_id, today)
        return total
