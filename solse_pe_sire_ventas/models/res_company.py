# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class ResCompany(models.Model) :
	_inherit = 'res.company'

	