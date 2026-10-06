# -*- coding: utf-8 -*-

from odoo import fields, models


class ResCompany(models.Model):
	_inherit = 'res.company'

	afecto_senati = fields.Boolean(
		string='Afecta a SENATI',
		help='Ley 26272: empresas que desarrollan actividad industrial '
			 '(categoría D CIIU) con más de 20 trabajadores. Activa el '
			 'cálculo de la contribución SENATI (0.75%) en la nómina.'
	)
