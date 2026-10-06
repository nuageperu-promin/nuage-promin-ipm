# -*- coding: utf-8 -*-

# Capa PE sobre hr.rule.parameter:
#  - Categorización para la vista amigable "Parámetros de Nómina PE".
#  - Verificación de vigencia de la RMA (tope de prima AFP, actualización
#    trimestral SBS) con aviso en el dashboard de nómina.

from datetime import timedelta

from odoo import api, fields, models, _


class HrRuleParameter(models.Model):
	_inherit = 'hr.rule.parameter'

	categoria_pe = fields.Selection(
		selection=[
			('generales', 'Generales (UIT, RMV, Asig. Familiar)'),
			('pensiones', 'Pensiones (ONP / AFP)'),
			('salud', 'Salud (ESSALUD / EPS)'),
			('renta', 'Renta de 5ta Categoría'),
			('beneficios', 'Beneficios sociales'),
			('jornada', 'Jornada (HHEE / nocturna)'),
			('otros', 'Otros'),
		],
		string='Categoría PE',
		help='Agrupa los parámetros de la localización peruana en la vista '
			 '"Parámetros de Nómina PE". Los parámetros sin categoría no aparecen ahí.'
	)

	# Días máximos de antigüedad tolerados para la vigencia de la RMA antes
	# de mostrar advertencia (la SBS la publica cada trimestre).
	DIAS_ALERTA_RMA = 95

	@api.model
	def verificar_vigencia_rma(self):
		"""Devuelve un dict con la advertencia si la RMA está desactualizada.

		Pensado para invocarse desde el warning del dashboard de nómina y
		desde el cron de verificación. Retorna {} si todo está vigente.
		"""
		parametro_id = self.env['hr.rule.parameter.value'].search([
			('code', '=', 'pe_afp_rma'),
		], order='date_from desc', limit=1)
		if not parametro_id:
			return {
				'titulo': _('Falta el parámetro RMA (pe_afp_rma)'),
				'detalle': _('No existe ningún valor cargado para la Remuneración '
							 'Máxima Asegurable de la prima de seguro AFP.'),
			}
		hoy = fields.Date.context_today(self)
		limite = parametro_id.date_from + timedelta(days=self.DIAS_ALERTA_RMA)
		if hoy > limite:
			return {
				'titulo': _('RMA de AFP posiblemente desactualizada'),
				'detalle': _('La última vigencia cargada de la Remuneración Máxima '
							 'Asegurable (tope de prima de seguro AFP) es del %s. '
							 'La SBS actualiza este tope cada trimestre: verifique el '
							 'valor vigente en el portal de la SBS y registre la nueva '
							 'vigencia en Parámetros de Nómina PE.') % (
								fields.Date.to_string(parametro_id.date_from)),
			}
		return {}
