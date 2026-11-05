# -*- coding: utf-8 -*-
import logging

from odoo import api, models
from odoo.tools import SQL

_logger = logging.getLogger(__name__)


class AccountReport(models.Model):
    _inherit = 'account.report'

    def _currency_table_apply_rate(self, value):
        ctx = self.env.context
        if ctx.get('nuage_balance_usd') and getattr(value, 'code', None) == 'account_partial_reconcile.amount':
            modo = ctx.get('nuage_cf_modo')
            if modo == 'liq':
                # Líneas del asiento de pago: se toma el lado de esa línea.
                return SQL(
                    'CASE WHEN account_partial_reconcile.credit_move_id = account_move_line.id '
                    'THEN account_partial_reconcile.nuage_credit_usd '
                    'ELSE account_partial_reconcile.nuage_debit_usd END')
            if modo == 'rec':
                # Líneas de la factura: el lado que no pertenece al asiento de pago.
                return SQL(
                    'CASE WHEN debit_line.move_id IN (SELECT unnest(payment_move_ids.move_id) FROM payment_move_ids) '
                    'THEN account_partial_reconcile.nuage_credit_usd '
                    'ELSE account_partial_reconcile.nuage_debit_usd END')
        return super()._currency_table_apply_rate(value)

    @api.model
    def _nuage_crear_variante_flujo_usd(self):
        """Crea (una sola vez) la variante en USD del Estado de Flujos de Efectivo."""
        raiz = self.with_context(lang='en_US').search([
            ('custom_handler_model_name', '=', 'account.cash.flow.report.handler'),
            ('root_report_id', '=', False)], limit=1)
        if not raiz:
            return
        variante = self.search([('root_report_id', '=', raiz.id), ('nuage_moneda_fija', '=', 'USD')], limit=1)
        try:
            with self.env.cr.savepoint():
                if not variante:
                    variante = raiz.copy({'root_report_id': raiz.id, 'nuage_moneda_fija': 'USD'})
                variante._nuage_fijar_nombre('Estado de Flujos de Efectivo (USD)')
                raiz._nuage_fijar_nombre('Estado de Flujos de Efectivo (SOL)')
        except Exception:
            _logger.warning('No se pudo crear la variante del flujo de efectivo en USD', exc_info=True)
