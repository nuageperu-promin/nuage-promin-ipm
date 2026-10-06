# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PlameSuspensionCuarta(models.Model):
	_name = 'plame.suspension.cuarta'
	_description = 'Constancia de suspensión de retenciones de 4ta categoría'
	_order = 'ejercicio desc, fecha_desde desc'
	_rec_name = 'numero_constancia'

	partner_id = fields.Many2one(
		'res.partner',
		string='Prestador',
		required=True,
		ondelete='cascade',
		index=True,
	)
	ejercicio = fields.Char(
		string='Ejercicio',
		required=True,
		size=4,
		help="Año al que corresponde la constancia. Las constancias de "
		     "suspensión son anuales.",
	)
	numero_constancia = fields.Char(
		string='N° de constancia',
		required=True,
	)
	fecha_desde = fields.Date(
		string='Vigente desde',
		required=True,
	)
	fecha_hasta = fields.Date(
		string='Vigente hasta',
		help="Si se deja vacío, se asume vigente hasta el 31 de diciembre "
		     "del ejercicio indicado.",
	)
	nota = fields.Char(string='Observación')

	@api.constrains('ejercicio')
	def _verificar_ejercicio(self):
		for registro in self:
			if not (registro.ejercicio or '').isdigit() or len(registro.ejercicio) != 4:
				raise ValidationError(
					_("El ejercicio debe ser un año de 4 dígitos (valor "
					  "ingresado: %s).") % registro.ejercicio
				)

	@api.constrains('fecha_desde', 'fecha_hasta')
	def _verificar_rango_fechas(self):
		for registro in self:
			if registro.fecha_hasta and registro.fecha_hasta < registro.fecha_desde:
				raise ValidationError(
					_("La fecha final de vigencia de la constancia %s no puede "
					  "ser anterior a la inicial.") % registro.numero_constancia
				)

	def esta_vigente_en(self, fecha):
		"""Indica si alguna de las constancias del recordset cubre la fecha."""
		if not fecha:
			return False
		for registro in self:
			if fecha < registro.fecha_desde:
				continue
			if registro.fecha_hasta:
				if fecha <= registro.fecha_hasta:
					return True
				continue
			# Sin fecha final: se asume todo el ejercicio.
			if str(fecha.year) == registro.ejercicio:
				return True
		return False
