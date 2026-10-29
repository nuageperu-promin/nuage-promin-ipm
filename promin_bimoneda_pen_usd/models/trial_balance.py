# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
from odoo import models


class TrialBalanceHandler(models.AbstractModel):
    _inherit = 'account.trial.balance.report.handler'

    def _report_custom_engine_trial_balance(self, expressions, options, *args, **kwargs):
        if options.get('nuage_moneda') == 'USD':
            self = self.with_context(nuage_balance_usd=True)
        return super(TrialBalanceHandler, self)._report_custom_engine_trial_balance(
            expressions, options, *args, **kwargs)

    def _custom_line_postprocessor(self, report, options, lines):
        # La línea de resultados no distribuidos se calcula fuera del motor.
        if options.get('nuage_moneda') == 'USD':
            report = report.with_context(nuage_balance_usd=True)
        return super()._custom_line_postprocessor(report, options, lines)
