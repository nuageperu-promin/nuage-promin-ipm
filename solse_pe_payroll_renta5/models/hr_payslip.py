# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC

# Detalle de la retención de renta de 5ta (art. 40 Rgto. LIR).
#
# La regla R5TA_001 de solse_pe_payroll calcula todos los pasos pero solo
# deja el monto final en el recibo. Aquí se reconstruye el mismo cálculo,
# con los mismos parámetros (payslip._rule_parameter) y los mismos
# acumulados (payslip._sum, que solo suma boletas VALIDADAS o PAGADAS), y
# se guarda como foto del momento en que se calculó la hoja. La regla no
# se modifica: si el resultado reconstruido no coincide con la línea
# R5TA_001, el detalle queda marcado como «Difiere de la boleta».

import logging
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import Command, fields, models

_logger = logging.getLogger(__name__)

CODIGO_REGLA = 'R5TA_001'
CODIGO_BASE_ACUMULADA = 'BAR5_001'
CODIGO_CATEGORIA_AFECTA = 'INA_001'
TOLERANCIA = 0.01

# Meses de abril a noviembre: (último mes de las retenciones previas, divisor)
DOZAVOS = {
	4: (3, 9.0),
	5: (4, 8.0), 6: (4, 8.0), 7: (4, 8.0),
	8: (7, 5.0),
	9: (8, 4.0), 10: (8, 4.0), 11: (8, 4.0),
}
NOMBRES_MES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
			   'agosto', 'setiembre', 'octubre', 'noviembre', 'diciembre']


class HrPayslip(models.Model):
	_inherit = 'hr.payslip'

	pe_r5_estado = fields.Selection(
		string='Detalle de 5ta',
		selection=[
			('no_calculado', 'Sin calcular'),
			('no_aplica', 'No aplica'),
			('coincide', 'Coincide con la boleta'),
			('diferencia', 'Difiere de la boleta'),
			('error', 'Error al calcular'),
		],
		default='no_calculado', readonly=True, copy=False, index=True)
	pe_r5_mensaje = fields.Char(string='Observación', readonly=True, copy=False)
	pe_r5_fecha_calculo = fields.Datetime(string='Detalle calculado el', readonly=True, copy=False)

	# Parámetros usados
	pe_r5_uit = fields.Monetary(string='UIT', readonly=True, copy=False)
	pe_r5_regimen = fields.Char(string='Régimen laboral', readonly=True, copy=False)
	pe_r5_factor_grati = fields.Float(string='Factor de gratificación', readonly=True, copy=False)
	pe_r5_bono_tasa = fields.Float(string='Bonificación extraordinaria (%)', readonly=True, copy=False)

	# Paso 1: proyección anual
	pe_r5_base_mes = fields.Monetary(
		string='Remuneración afecta del mes', readonly=True, copy=False,
		help='Ingresos afectos (categoría INA_001) calculados antes de la regla de 5ta.')
	pe_r5_meses_restantes = fields.Integer(string='Meses por proyectar', readonly=True, copy=False)
	pe_r5_proyeccion_remuneraciones = fields.Monetary(
		string='Remuneraciones proyectadas', readonly=True, copy=False)
	pe_r5_percibido = fields.Monetary(
		string='Percibido en meses anteriores', readonly=True, copy=False,
		help='Suma de la base afecta (BAR5_001) de las boletas validadas o pagadas del año, '
			 'desde enero hasta el mes anterior.')
	pe_r5_sueldo = fields.Monetary(string='Sueldo del contrato', readonly=True, copy=False)
	pe_r5_gratis_pendientes = fields.Integer(string='Gratificaciones por percibir', readonly=True, copy=False)
	pe_r5_proyeccion_gratificaciones = fields.Monetary(
		string='Gratificaciones proyectadas', readonly=True, copy=False)
	pe_r5_renta_bruta = fields.Monetary(string='Renta bruta anual proyectada', readonly=True, copy=False)

	# Paso 2: deducción
	pe_r5_deduccion_uit = fields.Float(string='Deducción (UIT)', readonly=True, copy=False)
	pe_r5_deduccion = fields.Monetary(string='Deducción', readonly=True, copy=False)
	pe_r5_renta_neta = fields.Monetary(string='Renta neta anual', readonly=True, copy=False)

	# Paso 3: tramos
	pe_r5_tramo_ids = fields.One2many(
		'pe.renta5.tramo', 'payslip_id', string='Tramos aplicados', readonly=True, copy=False)
	pe_r5_impuesto_anual = fields.Monetary(string='Impuesto anual proyectado', readonly=True, copy=False)

	# Paso 4: retención del mes
	pe_r5_regla_mes = fields.Char(string='Regla del mes', readonly=True, copy=False)
	pe_r5_retenciones_previas = fields.Monetary(
		string='Retenciones previas del año', readonly=True, copy=False)
	pe_r5_retencion_calculada = fields.Monetary(string='Retención calculada', readonly=True, copy=False)
	pe_r5_retencion_boleta = fields.Monetary(string='Retención en la boleta', readonly=True, copy=False)
	pe_r5_diferencia = fields.Monetary(string='Diferencia', readonly=True, copy=False)

	# ------------------------------------------------------------------
	# Disparadores
	# ------------------------------------------------------------------
	def compute_sheet(self):
		resultado = super().compute_sheet()
		self._pe_r5_actualizar_detalle()
		return resultado

	def action_pe_r5_actualizar(self):
		self._pe_r5_actualizar_detalle()
		return True

	def action_pe_r5_imprimir(self):
		return self.env.ref(
			'solse_pe_payroll_renta5.action_reporte_detalle_renta5').report_action(self)

	def _pe_r5_actualizar_detalle(self):
		"""El detalle es informativo: un error aquí nunca debe impedir
		calcular la nómina. Se registra en el log y en el propio recibo."""
		for boleta in self:
			try:
				with self.env.cr.savepoint():
					boleta._pe_r5_guardar(boleta._pe_r5_calcular())
			except Exception as error:  # noqa: BLE001 - ver docstring
				_logger.exception('Detalle de renta de 5ta: error en el recibo %s', boleta.id)
				boleta._pe_r5_guardar({
					'pe_r5_estado': 'error',
					'pe_r5_mensaje': str(error)[:250],
				})

	def _pe_r5_guardar(self, valores):
		self.ensure_one()
		tramos = valores.pop('tramos', [])
		valores.update({
			'pe_r5_fecha_calculo': fields.Datetime.now(),
			'pe_r5_tramo_ids': [Command.clear()] + [Command.create(tramo) for tramo in tramos],
		})
		self.write(valores)

	# ------------------------------------------------------------------
	# Cálculo (mismo algoritmo que la regla R5TA_001)
	# ------------------------------------------------------------------
	def _pe_r5_calcular(self):
		self.ensure_one()
		linea_regla = self.line_ids.filtered(lambda linea: linea.code == CODIGO_REGLA)[:1]
		if not linea_regla:
			return {
				'pe_r5_estado': 'no_aplica',
				'pe_r5_mensaje': 'Este recibo no tiene la línea de renta de 5ta (R5TA_001): su '
								 'estructura no la incluye o no corresponde, por ejemplo en '
								 'nóminas semanales o de beneficios.',
			}

		anio, mes = self.date_from.year, self.date_from.month
		inicio_anio = date(anio, 1, 1)
		uit = self._rule_parameter('pe_uit')
		deduccion_uit = self._rule_parameter('pe_renta5_deduccion_uit')
		deduccion = deduccion_uit * uit
		tramos = self._rule_parameter('pe_renta5_tramos')
		factores = self._rule_parameter('pe_regimen_factores')

		version = self.version_id
		clave_regimen = version.labor_regime_id.clave_regimen or 'general'
		factor_grati = factores.get(clave_regimen, (1.0, 30, 30))[0]

		# 1) Proyección anual
		base_mes = self._pe_r5_base_mes(linea_regla)
		percibido = 0.0
		if mes > 1:
			fin_mes_anterior = date(anio, mes, 1) - relativedelta(days=1)
			percibido = self._sum(CODIGO_BASE_ACUMULADA, inicio_anio, fin_mes_anterior)
		meses_restantes = 12 - mes + 1
		proyeccion_remuneraciones = base_mes * meses_restantes

		codigo_bono = 'pe_grati_bono_eps' if self.employee_id.management_eps else 'pe_grati_bono_essalud'
		bono = self._rule_parameter(codigo_bono)
		gratis_pendientes = len([m for m in (7, 12) if m >= mes])
		proyeccion_gratis = version.wage * factor_grati * (1.0 + bono) * gratis_pendientes
		renta_bruta = percibido + proyeccion_remuneraciones + proyeccion_gratis

		# 2) Deducción de 7 UIT
		renta_neta = renta_bruta - deduccion

		# 3) Tramos progresivos y 4) dozavo del mes
		detalle_tramos, impuesto = self._pe_r5_tramos(renta_neta, tramos, uit)
		previas, regla_mes, retencion = self._pe_r5_retencion_mes(impuesto, anio, mes, renta_neta)

		retencion_boleta = linea_regla.total
		diferencia = round(retencion, 2) - retencion_boleta
		coincide = abs(diferencia) <= TOLERANCIA
		if coincide:
			mensaje = 'El detalle reproduce la retención de la boleta.'
		else:
			mensaje = ('La retención reconstruida (%.2f) no coincide con la de la boleta (%.2f). '
					   'Revise si la regla R5TA_001 fue modificada o si cambiaron boletas '
					   'anteriores después de calcular esta.') % (retencion, retencion_boleta)

		return {
			'pe_r5_estado': 'coincide' if coincide else 'diferencia',
			'pe_r5_mensaje': mensaje,
			'pe_r5_uit': uit,
			'pe_r5_regimen': dict(self.env['employee.regime']._fields['clave_regimen'].selection).get(
				clave_regimen, clave_regimen),
			'pe_r5_factor_grati': factor_grati,
			'pe_r5_bono_tasa': bono * 100.0,
			'pe_r5_base_mes': base_mes,
			'pe_r5_meses_restantes': meses_restantes,
			'pe_r5_proyeccion_remuneraciones': proyeccion_remuneraciones,
			'pe_r5_percibido': percibido,
			'pe_r5_sueldo': version.wage,
			'pe_r5_gratis_pendientes': gratis_pendientes,
			'pe_r5_proyeccion_gratificaciones': proyeccion_gratis,
			'pe_r5_renta_bruta': renta_bruta,
			'pe_r5_deduccion_uit': deduccion_uit,
			'pe_r5_deduccion': deduccion,
			'pe_r5_renta_neta': renta_neta,
			'pe_r5_impuesto_anual': impuesto,
			'pe_r5_regla_mes': regla_mes,
			'pe_r5_retenciones_previas': previas,
			'pe_r5_retencion_calculada': retencion,
			'pe_r5_retencion_boleta': retencion_boleta,
			'pe_r5_diferencia': diferencia,
			'tramos': detalle_tramos,
		}

	def _pe_r5_base_mes(self, linea_regla):
		"""Equivale a categories['INA_001'] al momento de ejecutar la regla:
		suma de las líneas de la categoría INA_001 (o de sus subcategorías)
		con secuencia anterior a R5TA_001."""
		def es_afecta(categoria):
			while categoria:
				if categoria.code == CODIGO_CATEGORIA_AFECTA:
					return True
				categoria = categoria.parent_id
			return False

		return sum(self.line_ids.filtered(
			lambda linea: linea.sequence < linea_regla.sequence and es_afecta(linea.category_id)
		).mapped('total'))

	def _pe_r5_tramos(self, renta_neta, tramos, uit):
		detalle, impuesto, limite_anterior = [], 0.0, 0.0
		if renta_neta <= 0:
			return detalle, impuesto
		for secuencia, (limite_uit, tasa) in enumerate(tramos, start=1):
			tope = (limite_uit * uit) if limite_uit else renta_neta
			tramo = min(renta_neta, tope) - limite_anterior
			if tramo <= 0:
				break
			impuesto += tramo * tasa
			detalle.append({
				'secuencia': secuencia,
				'desde': limite_anterior,
				'hasta': (limite_uit * uit) if limite_uit else 0.0,
				'limite_uit': limite_uit or 0.0,
				'tasa': tasa * 100.0,
				'base_tramo': tramo,
				'impuesto': tramo * tasa,
			})
			limite_anterior = tope
		return detalle, impuesto

	def _pe_r5_retencion_mes(self, impuesto, anio, mes, renta_neta):
		"""Devuelve (retenciones previas, texto de la regla aplicada, retención)."""
		if renta_neta <= 0:
			return 0.0, 'La renta neta anual no supera la deducción: no corresponde retener.', 0.0
		inicio_anio = date(anio, 1, 1)
		if mes <= 3:
			return 0.0, 'Enero a marzo: impuesto anual ÷ 12.', max(impuesto / 12.0, 0.0)
		ultimo_mes = DOZAVOS.get(mes, (11, 1.0))[0]
		previas = self._sum(CODIGO_REGLA, inicio_anio,
							date(anio, ultimo_mes + 1, 1) - relativedelta(days=1))
		hasta = NOMBRES_MES[ultimo_mes - 1]
		if mes == 12:
			texto = 'Diciembre: impuesto anual − retenciones de enero a noviembre (saldo).'
			return previas, texto, max(impuesto - previas, 0.0)
		divisor = DOZAVOS[mes][1]
		texto = '%s: (impuesto anual − retenciones de enero a %s) ÷ %d.' % (
			NOMBRES_MES[mes - 1].capitalize(), hasta, divisor)
		return previas, texto, max((impuesto - previas) / divisor, 0.0)
