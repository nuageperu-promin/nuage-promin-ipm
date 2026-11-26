from odoo import api, models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _nuage_tc_aplica(self):
        self.ensure_one()
        return (self.is_invoice(include_receipts=True)
                and self.currency_id.name == 'USD'
                and (self.invoice_date or self.date))

    @api.onchange('invoice_date', 'date', 'currency_id')
    def _onchange_nuage_tc(self):
        Cur = self.env['res.currency']
        for move in self:
            if not move._nuage_tc_aplica():
                continue
            fecha = move.invoice_date or move.date
            estado, usada = Cur._nuage_asegurar_tc(fecha, move.company_id)
            if estado in ('exacta', 'previa'):
                move._compute_invoice_currency_rate()
            if estado == 'falta':
                return {'warning': {
                    'title': _('Tipo de cambio'),
                    'message': _('No se encontró tipo de cambio para %s ni en los días hábiles anteriores. '
                                 'Verifique la fecha o registre la tasa manualmente.', fecha)}}

    def action_post(self):
        Cur = self.env['res.currency']
        for move in self:
            if not move._nuage_tc_aplica():
                continue
            fecha = move.invoice_date or move.date
            estado, usada = Cur._nuage_asegurar_tc(fecha, move.company_id)
            if estado == 'falta':
                raise UserError(_(
                    'No hay tipo de cambio USD para %s ni en los 7 días anteriores. '
                    'Registre la tasa antes de confirmar.', fecha))
            if estado == 'previa':
                move.message_post(body=_(
                    'Sin tipo de cambio publicado para %(f)s; se usó el del %(u)s.',
                    f=fecha, u=usada))
        return super().action_post()
