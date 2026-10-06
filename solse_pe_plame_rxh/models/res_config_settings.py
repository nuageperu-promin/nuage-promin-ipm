# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
	_inherit = 'res.config.settings'

	plame_regimen_pensionario = fields.Selection(
		related='company_id.plame_regimen_pensionario',
		readonly=False,
	)
	plame_rellenar_numero = fields.Boolean(
		related='company_id.plame_rellenar_numero',
		readonly=False,
	)
	plame_dias_tolerancia_emision = fields.Integer(
		related='company_id.plame_dias_tolerancia_emision',
		readonly=False,
	)
