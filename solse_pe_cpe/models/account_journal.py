# -*- coding: utf-8 -*-

from odoo import api, fields, tools, models, _
from odoo.exceptions import UserError, RedirectWarning
import logging
_logging = logging.getLogger(__name__)


class AccountJournal(models.Model):
	_inherit = 'account.journal'

	tipo_doc_permitidos = fields.Many2many("l10n_latam.document.type", "diario_id", "tipo_doc_id", "diario_tipo_id", string="Documentos Permitidos")
	mostrar_impuestos_en_cero = fields.Boolean("Mostrar impuestos en cero", default=True)

	
class ResCurrency(models.Model):
	_inherit = 'res.currency'

	def currency_compute(self, from_amount, to_currency, round=True):
		_logging.info('The `compute` method is deprecated. Use `_convert` instead')
		date = self.env.context.get('date') or fields.Date.today()
		company = self.env['res.company'].browse(self.env.context.get('company_id')) or self.env.company
		return self._convert(from_amount, to_currency, company, date)