# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
import logging

from odoo import api, models
from odoo.tools import SQL

_logger = logging.getLogger(__name__)

# Saldo pendiente de cada movimiento tal como lo arma Odoo en la antigüedad de saldos.
SALDO_PENDIENTE = ('account_move_line.balance - COALESCE(part_debit.amount, 0) '
                   '+ COALESCE(part_credit.amount, 0)')


class AccountReport(models.Model):
    _inherit = 'account.report'

    def _currency_table_apply_rate(self, value):
        if self.env.context.get('nuage_balance_usd'):
            codigo = ' '.join((getattr(value, 'code', None) or '').split())
            if codigo == SALDO_PENDIENTE:
                # Saldo pendiente en USD = saldo pendiente en soles x (USD / soles del movimiento),
                # es decir, con el tipo de cambio de la fecha del movimiento.
                return SQL(
                    'CASE WHEN account_move_line.balance <> 0 '
                    'THEN (%s) * account_move_line.nuage_balance_usd / account_move_line.balance '
                    'ELSE 0 END', value)
        return super()._currency_table_apply_rate(value)

    def _format_value(self, options, value, figure_type, format_params=None):
        # En la variante USD los montos se muestran con el símbolo del dólar (por defecto Odoo
        # usa la moneda de la compañía). Las columnas que ya traen su propia moneda no se tocan.
        if (options.get('nuage_moneda') == 'USD' and figure_type == 'monetary'
                and 'currency_id' not in (format_params or {})):
            format_params = dict(format_params or {}, currency_id=self.env.ref('base.USD').id)
        return super()._format_value(options, value, figure_type, format_params=format_params)

    @api.model
    def _nuage_crear_variantes_antiguedad_usd(self):
        """Crea (una sola vez) la variante en USD de la antigüedad de cuentas por cobrar y por
        pagar, y rotula los originales como (SOL)."""
        manejadores = {
            'account.aged.receivable.report.handler': 'Cuenta por cobrar vencida',
            'account.aged.payable.report.handler': 'Cuenta por pagar vencida',
        }
        for handler, nombre in manejadores.items():
            raiz = self.with_context(lang='en_US').search([
                ('custom_handler_model_name', '=', handler), ('root_report_id', '=', False)], limit=1)
            if not raiz:
                continue
            variante = self.search([('root_report_id', '=', raiz.id), ('nuage_moneda_fija', '=', 'USD')], limit=1)
            try:
                with self.env.cr.savepoint():
                    if not variante:
                        variante = raiz.copy({'root_report_id': raiz.id, 'nuage_moneda_fija': 'USD'})
                    variante._nuage_fijar_nombre('%s (USD)' % nombre)
                    raiz._nuage_fijar_nombre('%s (SOL)' % nombre)
            except Exception:
                _logger.warning('No se pudo crear la variante en USD de %s', nombre, exc_info=True)
