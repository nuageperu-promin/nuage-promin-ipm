# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountPartialReconcile(models.Model):
    _inherit = 'account.partial.reconcile'

    nuage_debit_usd = fields.Float(
        'Importe USD (lado débito)', compute='_compute_nuage_usd', store=True, digits=(16, 6),
        help='Parte de la conciliación valuada en dólares con el tipo de cambio de la línea de débito.')
    nuage_credit_usd = fields.Float(
        'Importe USD (lado crédito)', compute='_compute_nuage_usd', store=True, digits=(16, 6),
        help='Parte de la conciliación valuada en dólares con el tipo de cambio de la línea de crédito.')

    @api.depends('amount', 'debit_move_id.balance', 'debit_move_id.nuage_balance_usd',
                 'credit_move_id.balance', 'credit_move_id.nuage_balance_usd')
    def _compute_nuage_usd(self):
        for p in self:
            d, c = p.debit_move_id, p.credit_move_id
            p.nuage_debit_usd = p.amount * d.nuage_balance_usd / d.balance if d.balance else 0.0
            p.nuage_credit_usd = p.amount * c.nuage_balance_usd / c.balance if c.balance else 0.0
