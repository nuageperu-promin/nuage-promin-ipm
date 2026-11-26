from datetime import timedelta
from odoo import api, models


class ResCurrencyRate(models.Model):
    _inherit = 'res.currency.rate'

    def _nuage_refrescar_borradores(self):
        Move = self.env['account.move'].sudo()
        for rate in self:
            if not rate.name or not rate.company_id:
                continue
            ini, fin = rate.name, rate.name + timedelta(days=6)
            moves = Move.search([
                ('state', '=', 'draft'),
                ('company_id', '=', rate.company_id.id),
                ('currency_id', '=', rate.currency_id.id),
                '|',
                '&', ('invoice_date', '>=', ini), ('invoice_date', '<=', fin),
                '&', ('invoice_date', '=', False), '&', ('date', '>=', ini), ('date', '<=', fin),
            ])
            if moves:
                moves.invalidate_recordset(['invoice_currency_rate'])
                moves._compute_invoice_currency_rate()

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._nuage_refrescar_borradores()
        return recs

    def write(self, vals):
        res = super().write(vals)
        if 'rate' in vals or 'name' in vals:
            self._nuage_refrescar_borradores()
        return res
