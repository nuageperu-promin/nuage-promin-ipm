# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class Bank(models.Model) :
	_inherit = 'res.bank'
	
	l10n_pe_bank_code = fields.Selection(selection="_get_pe_banco", string='Banco')

	@api.model
	def _get_pe_banco(self):
		return self.env['pe.datas'].get_selection("PE.TABLA03")
