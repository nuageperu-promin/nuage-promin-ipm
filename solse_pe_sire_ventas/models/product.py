# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
import logging
_logging = logging.getLogger(__name__)

class ProductTemplate(models.Model):
	_inherit = 'product.template'

	@api.model
	def _get_pe_bien_servicio(self):
		return self.env['pe.datas'].get_selection("PE.TABLA30")

	tipo_bien_servicio = fields.Selection("_get_pe_bien_servicio", "Tipo de Bien/Servicio")