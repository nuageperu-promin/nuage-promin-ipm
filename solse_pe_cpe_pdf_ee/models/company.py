# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class Company(models.Model):
	_inherit = "res.company"

	formato_defecto = fields.Selection([("formato_n1", "Formato n1")], default="formato_n1", string="Formato")