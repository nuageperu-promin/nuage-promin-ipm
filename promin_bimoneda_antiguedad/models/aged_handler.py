# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
from odoo import models


class AgedPartnerBalanceHandler(models.AbstractModel):
    _inherit = 'account.aged.partner.balance.report.handler'

    def _report_custom_engine_aged_receivable(self, expressions, options, date_scope, current_groupby,
                                              next_groupby, offset=0, limit=None, warnings=None):
        if options.get('nuage_moneda') == 'USD':
            self = self.with_context(nuage_balance_usd=True)
        return super(AgedPartnerBalanceHandler, self)._report_custom_engine_aged_receivable(
            expressions, options, date_scope, current_groupby, next_groupby,
            offset=offset, limit=limit, warnings=warnings)

    def _report_custom_engine_aged_payable(self, expressions, options, date_scope, current_groupby,
                                           next_groupby, offset=0, limit=None, warnings=None):
        if options.get('nuage_moneda') == 'USD':
            self = self.with_context(nuage_balance_usd=True)
        return super(AgedPartnerBalanceHandler, self)._report_custom_engine_aged_payable(
            expressions, options, date_scope, current_groupby, next_groupby,
            offset=offset, limit=limit, warnings=warnings)
