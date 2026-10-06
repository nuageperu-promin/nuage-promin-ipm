# -*- coding: utf-8 -*-

from odoo import models, fields, api
import unicodedata

class District(models.Model):
	_description = "Distrito"
	_inherit = 'l10n_pe.res.city.district'
	
	name_simple = fields.Char('Nombre simple', compute='_compute_nombre_simple', store=True)

	@api.depends('name')
	def _compute_nombre_simple(self):
		for reg in self:
			# Validamos si reg.name tiene contenido, si no, usamos una cadena vacía ''
			name_text = reg.name or ''
			
			# Ahora procesamos con la seguridad de que siempre será un string
			reg.name_simple = unicodedata.normalize('NFKD', name_text).encode('ASCII', 'ignore').strip().upper().decode()