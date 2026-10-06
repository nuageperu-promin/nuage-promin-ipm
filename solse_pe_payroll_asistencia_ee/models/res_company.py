# -*- coding: utf-8 -*-

from odoo import fields, models


class ResCompany(models.Model):
	_inherit = 'res.company'

	asistencia_tolerancia_minutos = fields.Integer(
		string='Tolerancia de tardanza (minutos)', default=10,
		help='Minutos de gracia sobre la hora de entrada del calendario '
			 'antes de contar tardanza.')
	asistencia_descontar_tardanzas = fields.Boolean(
		string='Descontar tardanzas en la boleta', default=True,
		help='Si está apagado, la conciliación reporta las tardanzas en el '
			 'resumen pero no genera el descuento.')
	asistencia_autocargar = fields.Boolean(
		string='Conciliar asistencias al calcular la boleta', default=False,
		help='Si está activo, "Calcular hoja" ejecuta la conciliación de '
			 'asistencias automáticamente en boletas en borrador.')

	# --- Fase 2: evaluación proporcional por horas ---
	asistencia_evaluar_horas = fields.Boolean(
		string='Evaluar horas trabajadas por día', default=False,
		help='Fase 2: además de faltas de día completo, descuenta las '
			 'horas no trabajadas del día (salidas tempranas, medias '
			 'jornadas) como fracción de día no pagada.')
	asistencia_margen_horas = fields.Float(
		string='Margen de horas por día', default=0.25,
		help='Horas faltantes iguales o menores a este margen se ignoran '
			 '(ruido de marcación). 0.25 = 15 minutos.')
