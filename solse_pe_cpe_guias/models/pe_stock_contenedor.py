# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PeStockContenedor(models.Model):
	_name = 'pe.stock.contenedor'
	_description = 'Contenedor / Equipo de Transporte de Guía Electrónica'
	_order = 'sequence, id'

	picking_id = fields.Many2one(
		comodel_name='stock.picking',
		string='Guía',
		required=True,
		ondelete='cascade',
		index=True,
	)
	sequence = fields.Integer(string='Secuencia', default=10)

	numero_contenedor = fields.Char(
		string='Número de contenedor',
		required=True,
		size=20,
		help="Número del contenedor que transporta los bienes. "
			 "Mapea a cac:TransportHandlingUnit/cac:TransportEquipment/cbc:ID."
	)
	numero_precinto = fields.Char(
		string='Número de precinto',
		size=15,
		help="Número del precinto de seguridad del contenedor. "
			 "Mapea a cac:TransportHandlingUnit/cac:TransportEquipment/cbc:TraceID."
	)

	@api.constrains('numero_contenedor')
	def _validar_numero_contenedor(self):
		for registro in self:
			if not registro.numero_contenedor or not registro.numero_contenedor.strip():
				raise ValidationError(_(
					"El número de contenedor es obligatorio."
				))
			if len(registro.numero_contenedor.strip()) > 20:
				raise ValidationError(_(
					"El número de contenedor no debe exceder 20 caracteres."
				))
