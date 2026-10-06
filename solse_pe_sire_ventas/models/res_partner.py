# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class Partner(models.Model) :
	_inherit = 'res.partner'
	
	l10n_pe_worker_code = fields.Char(string='Código de Trabajador')
