# -*- coding: utf-8 -*-
"""Catálogos 63 y 64 de SUNAT: puertos y aeropuertos.

La GRE con motivo de traslado 08 (importación) o 09 (exportación) exige el
bloque `cac:FirstArrivalPortLocation` con el código del puerto (Catálogo
N° 63) o aeropuerto (Catálogo N° 64), el tipo de locación (1=puerto,
2=aeropuerto) y el nombre. Sin él, SUNAT rechaza con 3369 (exportación) o
3365 (importación); con un ubigeo inconsistente, con 3364.

Los registros sembrados provienen del anexo de la R.S. 123-2022/SUNAT
(códigos an3 alfabéticos con su ubigeo). El resto del anexo se puede
cargar por importación estándar.
"""

from odoo import models, fields, api


class SolsePePuerto(models.Model):
	_name = 'solse.pe.puerto'
	_description = 'Puertos y aeropuertos SUNAT (Catálogos 63 y 64)'
	_order = 'tipo, name'

	name = fields.Char('Nombre', required=True)
	codigo = fields.Char('Código SUNAT', size=3, required=True,
						 help='Código an3 del Catálogo 63 (puertos) o '
							  '64 (aeropuertos)')
	tipo = fields.Selection([
		('1', 'Puerto (Catálogo 63)'),
		('2', 'Aeropuerto (Catálogo 64)'),
	], string='Tipo de locación', required=True, default='1')
	ubigeo = fields.Char('Ubigeo', size=6,
						 help='Ubigeo del puerto según el anexo SUNAT. El '
							  'punto de llegada de la guía debe ser '
							  'consistente con él (error 3364).')
	active = fields.Boolean(default=True)

	_codigo_tipo_unico = models.Constraint(
		'unique(codigo, tipo)',
		'El código ya existe para ese tipo de locación.')

	# name_get no existe en Odoo 19; el reemplazo es _compute_display_name.
	@api.depends('codigo', 'name')
	def _compute_display_name(self):
		for reg in self:
			reg.display_name = '[%s] %s' % (reg.codigo or '', reg.name or '')
