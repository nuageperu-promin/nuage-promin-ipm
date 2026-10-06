# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
_logging = logging.getLogger(__name__)

class AccountPayment(models.Model) :
	_inherit = 'account.payment'
	
	l10n_pe_payment_method_code = fields.Selection(selection="_get_pe_medio_pago", string='Medio de Pago')

	@api.model
	def _get_pe_medio_pago(self):
		return self.env['pe.datas'].get_selection("PE.TABLA01")


class AccountPaymentRegister(models.TransientModel) :
	_inherit = 'account.payment.register'
	
	l10n_pe_payment_method_code = fields.Selection(selection="_get_pe_medio_pago", string='Medio de Pago')

	def _create_payment_vals_from_wizard(self, batch_result):
		payment_vals = super(AccountPaymentRegister, self)._create_payment_vals_from_wizard(batch_result)
		payment_vals['l10n_pe_payment_method_code'] = self.l10n_pe_payment_method_code
		return payment_vals

	def _create_payment_vals_from_batch(self, batch_result):
		batch_result['l10n_pe_payment_method_code'] = self.l10n_pe_payment_method_code
		batch_result['transaction_number'] = self.transaction_number
		payment_vals = super(AccountPaymentRegister, self)._create_payment_vals_from_batch(batch_result)
		payment_vals['l10n_pe_payment_method_code'] = self.l10n_pe_payment_method_code
		payment_vals['transaction_number'] = self.transaction_number
		return payment_vals

	@api.model
	def _get_pe_medio_pago(self):
		return self.env['pe.datas'].get_selection("PE.TABLA01")