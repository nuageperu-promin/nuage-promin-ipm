# -*- coding: utf-8 -*-
from odoo import models


class CashFlowHandler(models.AbstractModel):
    _inherit = 'account.cash.flow.report.handler'

    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals, warnings=None):
        if options.get('nuage_moneda') == 'USD':
            report = report.with_context(nuage_balance_usd=True)
            self = self.with_context(nuage_balance_usd=True)
        return super(CashFlowHandler, self)._dynamic_lines_generator(
            report, options, all_column_groups_expression_totals, warnings=warnings)

    def _get_liquidity_moves(self, report, options, *args, **kwargs):
        if options.get('nuage_moneda') == 'USD':
            report = report.with_context(nuage_cf_modo='liq')
        return super(CashFlowHandler, self)._get_liquidity_moves(report, options, *args, **kwargs)

    def _get_reconciled_moves(self, report, options, *args, **kwargs):
        if options.get('nuage_moneda') == 'USD':
            report = report.with_context(nuage_cf_modo='rec')
        return super(CashFlowHandler, self)._get_reconciled_moves(report, options, *args, **kwargs)

    def _get_unexplained_difference_line(self, report, options, report_data):
        linea = super(CashFlowHandler, self)._get_unexplained_difference_line(report, options, report_data)
        if linea:
            linea['name'] = ('Diferencia por tipo de cambio' if options.get('nuage_moneda') == 'USD'
                             else 'Diferencia no explicada')
        return linea
