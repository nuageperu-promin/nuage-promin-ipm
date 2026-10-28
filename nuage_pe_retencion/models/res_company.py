# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    nuage_retener_al_pagar = fields.Boolean(
        'Retener IGV al pagar (Nuage)', default=False,
        help='Si está activo, las facturas de proveedor ya no llevan la retención '
             'de Solse en el asiento. La retención se calcula al registrar el pago, '
             'sumando las facturas del mismo proveedor incluidas en la operación.')
    nuage_ret_tasa = fields.Float('Tasa de retención (%)', default=3.0, digits=(5, 2))
    nuage_ret_umbral = fields.Float(
        'Umbral de la operación (S/)', default=700.0, digits=(16, 2),
        help='Se retiene solo si la suma de las facturas retenibles del pago '
             'SUPERA este importe.')
    nuage_ret_serie = fields.Char(
        'Serie del comprobante', help='Por ejemplo RT01. Ver la serie autorizada ante SUNAT.')
    nuage_ret_correlativo_inicio = fields.Integer(
        'Correlativo inicial', default=1,
        help='El siguiente número será el mayor entre este valor y el último emitido + 1.')
    nuage_ret_cuenta_id = fields.Many2one(
        'account.account', 'Cuenta de IGV retenido por pagar',
        domain=[('account_type', 'not in', ['asset_receivable', 'liability_payable'])],
        help='Pasivo donde se acumula el IGV retenido a SUNAT. No puede ser una '
             'cuenta por pagar de proveedores.')
