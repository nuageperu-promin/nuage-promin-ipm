# -*- coding: utf-8 -*-

from odoo import fields, models

from .res_company import MODALIDAD_GUIA


class StockPickingType(models.Model):
	_inherit = "stock.picking.type"

	pe_guide_mode = fields.Selection(
		selection=MODALIDAD_GUIA,
		string='Modalidad de guía electrónica',
		help="Define si las transferencias de este tipo de operación emiten "
			 "Guía de Remisión Remitente (09) o Guía de Remisión "
			 "Transportista (31). Si se deja vacío se usa la modalidad "
			 "configurada en la compañía. El valor es editable por "
			 "transferencia.",
	)


class Warehouse(models.Model):
	_inherit = "stock.warehouse"

	eguide_transport_sequence_id = fields.Many2one(
		comodel_name='ir.sequence',
		string='Secuencia de guía electrónica transportista',
		help="Secuencia con prefijo V###- para la numeración de la GRT.",
	)
