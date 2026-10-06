# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class AccountPayment(models.Model) :
	_inherit = 'account.payment'
	
	l10n_pe_payment_method_code = fields.Selection(selection="_get_pe_medio_pago", string='Medio de Pago')

	@api.model
	def _get_pe_medio_pago(self):
		return self.env['pe.datas'].get_selection("PE.TABLA01")
