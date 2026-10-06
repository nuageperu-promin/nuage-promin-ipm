# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class Company(models.Model):
	_inherit = "res.company"

	pe_cpe_eguide_server_id = fields.Many2one(comodel_name="cpe.server", string="Servidor para Guías", domain="[('state','=','done')]")
