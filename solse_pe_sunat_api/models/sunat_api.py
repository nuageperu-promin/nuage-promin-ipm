# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class ApiSunat(models.Model):
	_name = 'solse.sunat.api'
	_description = 'API Sunat'

	name = fields.Char("Name", required=True)
	company_id = fields.Many2one("res.company", string="Empresa", default=lambda self: self.env.company.id)
	tipo = fields.Selection([("api", "Api"), ("apicomprobantes", "Api Comprobantes")], default="api", string="Tipo")
	user = fields.Char("Usuario")
	password = fields.Char("Clave")
	client_id = fields.Char("Id Cliente")
	client_secret = fields.Char("Clave Cliente")

	active= fields.Boolean("Active", default=True)
	
	_table_tipo_uniq = models.Constraint(
		'unique(company_id, tipo)',
		'Solo puede existir una credencial API por tipo y por compañía.')
	
	# M-48: aquí vivía un `get_selection(table_code)` copiado de `pe.datas`
	# que buscaba por `table_code`, campo que este modelo NO tiene. Nadie lo
	# llamaba, y llamarlo habría dado ValueError. Se elimina en vez de
	# arreglarlo: `pe.datas.get_selection` ya existe y es el que hay que usar.
