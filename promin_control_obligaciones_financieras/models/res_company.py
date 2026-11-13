# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    promin_obl_diario_id = fields.Many2one(
        'account.journal', string='Diario de asientos de obligaciones',
        domain="[('type', '=', 'general')]",
        help='Diario donde se registran los asientos de desembolso, pago de cuota y ajuste por diferencia de cambio.')
    promin_obl_cta_interes_id = fields.Many2one(
        'account.account', string='Cuenta de intereses',
        help='Gasto financiero. Ej.: 6731200 Intereses por préstamos.')
    promin_obl_cta_comision_id = fields.Many2one(
        'account.account', string='Cuenta de comisiones',
        help='Ej.: 6391000 Gastos bancarios - Comisiones.')
    promin_obl_cta_itf_id = fields.Many2one(
        'account.account', string='Cuenta de ITF / portes',
        help='Ej.: 6412000 Impuesto a las transacciones financieras.')
    promin_obl_cta_dc_ganancia_id = fields.Many2one(
        'account.account', string='Cuenta de ganancia por diferencia de cambio')
    promin_obl_cta_dc_perdida_id = fields.Many2one(
        'account.account', string='Cuenta de pérdida por diferencia de cambio')
    promin_obl_dias_alerta = fields.Integer(
        string='Días de anticipación de la alerta', default=7,
        help='Se crea una actividad para el responsable cuando faltan estos días (o menos) para el vencimiento.')
