# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class pe_sunat_server(models.Model):
	_inherit = 'cpe.server'

	es_guia = fields.Boolean("Es para guías")
	client_id = fields.Char("Id Cliente")
	client_secret = fields.Char("Clave Cliente")