# -*- coding: utf-8 -*-

from odoo import fields, models


class AccountTax(models.Model):
	_inherit = 'account.tax'

	es_retencion_cuarta = fields.Boolean(
		string='Retención de renta de 4ta categoría',
		default=False,
		help="Marque este impuesto si representa la retención del Impuesto a "
		     "la Renta de cuarta categoría (8%). El módulo PLAME lo usa para "
		     "determinar el campo 9 del archivo .4ta (indicador de retención) "
		     "y para excluirlo del monto bruto del servicio.",
	)
