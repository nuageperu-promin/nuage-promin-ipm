# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    nuage_balance_usd = fields.Float(
        string='Saldo USD (T.C. del movimiento)',
        compute='_compute_nuage_balance_usd', store=True,
        digits=(16, 6),
        help='Importe de la línea en dólares, fijado con el tipo de cambio de la '
             'fecha del movimiento. Si la operación es en USD se toma el importe '
             'original sin convertir. Base de la columna USD de los estados financieros.')

    @api.depends('balance', 'amount_currency', 'currency_id', 'date', 'company_id')
    def _compute_nuage_balance_usd(self):
        usd = self.env.ref('base.USD')
        for line in self:
            moneda_cia = line.company_currency_id
            if line.currency_id == usd and moneda_cia != usd:
                # Operación en dólares: importe original, sin conversión.
                line.nuage_balance_usd = line.amount_currency
            elif moneda_cia == usd:
                line.nuage_balance_usd = line.balance
            else:
                # Operación en soles u otra moneda: se pasa a USD con la tasa de la fecha.
                line.nuage_balance_usd = moneda_cia._convert(
                    line.balance, usd, line.company_id,
                    line.date or fields.Date.context_today(line), round=False)
