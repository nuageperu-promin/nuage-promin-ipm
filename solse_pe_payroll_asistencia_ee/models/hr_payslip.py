# -*- coding: utf-8 -*-

# Conciliación de asistencias (hr_attendance) contra la boleta ENTERPRISE.
# Gemelo de solse_pe_payroll_asistencia (Community), NEE hito 3.
#
# El MOTOR (_conciliar_periodo, _evaluar_dia, _horario_semana,
# _dias_con_ausencia_aprobada, _formatear_resumen) es copia literal del
# Community: no depende de la edición. La CAPA DE ESCRITURA se reescribió
# leyendo hr_payroll de Enterprise:
#
# - Falta = día laborable sin checada ni ausencia aprobada → línea de días
#   trabajados con work_entry_type FALTA. En EE `is_paid` es un compute
#   almacenado desde struct.unpaid_work_entry_type_ids
#   (hr_payslip_worked_days.py:21,32-35): NO se escribe; el tipo se declara
#   no pagado en la estructura (inicializador.configurar_asistencia_ee).
#   `code` y `version_id` son related (:17,:23): tampoco se escriben.
# - Tardanza = minutos netos de tolerancia → input TARDANZAS en horas, con
#   input_type_id required (hr_payslip_input.py:17); la regla TAR_001 lo
#   descuenta a valor hora (sueldo/240) con signo POSITIVO, como toda
#   deducción de solse_pe_payroll (NET = ING_001 − DED, bloque1:345).
# - Estado editable: solo `draft` (hr_payslip.py:66-70; `verify` no existe).
# - `action_refresh_from_work_entries` borra y regenera las líneas de días
#   (hr_payslip.py:809-811): se vuelve a conciliar detrás para no perder las
#   faltas en silencio. `compute_sheet` no las toca (:785-799).
#
# FASE 2 (preparado): _evaluar_dia() devuelve el detalle por día con horas
# esperadas y marcadas; la evaluación proporcional por horas se implementa
# sobreescribiendo solo ese método, sin tocar el esqueleto.

import logging
from datetime import datetime, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

CODIGO_FALTA = 'FALTA'
CODIGO_FALTA_PARCIAL = 'FALTA_PARCIAL'
CODIGO_TARDANZA = 'TARDANZAS'


class HrPayslip(models.Model):
	_inherit = 'hr.payslip'

	asistencia_resumen = fields.Text(
		string='Resumen de asistencias', readonly=True, copy=False,
		help='Resultado de la última conciliación de asistencias: días '
			 'evaluados, faltas y tardanzas, con el detalle por día.')

	# ------------------------------------------------------------------
	# Acción del botón
	# ------------------------------------------------------------------
	def accion_cargar_asistencias(self):
		for boleta_id in self:
			boleta_id._cargar_asistencias()
		return True

	def compute_sheet(self):
		# EE: `compute_sheet` solo procesa boletas en `draft`
		# (hr_payslip.py:786); se concilia con el mismo criterio.
		for boleta_id in self:
			if (boleta_id.company_id.asistencia_autocargar
					and boleta_id.state == 'draft'):
				boleta_id._cargar_asistencias(silencioso=True)
		return super().compute_sheet()

	def action_refresh_from_work_entries(self):
		"""El botón nativo borra y regenera las líneas de días desde las
		entradas de trabajo (hr_payslip.py:809-811), y con ellas se irían
		las líneas FALTA / FALTA_PARCIAL sin aviso. Toda boleta que ya se
		había conciliado se vuelve a conciliar detrás."""
		conciliadas = self.filtered('asistencia_resumen')
		resultado = super().action_refresh_from_work_entries()
		for boleta_id in conciliadas:
			if boleta_id.state == 'draft':
				boleta_id._cargar_asistencias(silencioso=True)
				boleta_id.compute_sheet()
		return resultado

	# ------------------------------------------------------------------
	# Motor
	# ------------------------------------------------------------------
	def _cargar_asistencias(self, silencioso=False):
		self.ensure_one()
		if self.state != 'draft':
			if silencioso:
				return False
			raise UserError(_(
				'La conciliación de asistencias solo aplica sobre boletas '
				'en borrador. Cancele la boleta para recalcularla.'))
		version_id = self.version_id or self.employee_id.version_id
		calendario_id = (version_id.resource_calendar_id
						 or self.employee_id.resource_calendar_id
						 or self.company_id.resource_calendar_id)
		if not calendario_id:
			raise UserError(_(
				'El empleado %s no tiene calendario laboral asignado.')
				% self.employee_id.name)

		detalle = self._conciliar_periodo(version_id, calendario_id)
		faltas = [d for d in detalle if d['estado'] == 'falta']
		minutos_tarde = sum(d['minutos_tarde'] for d in detalle)
		horas_faltantes = sum(
			d.get('horas_faltantes', 0.0) for d in detalle)
		self._escribir_faltas(version_id, len(faltas))
		self._escribir_faltas_parciales(version_id, horas_faltantes)
		self._escribir_tardanzas(minutos_tarde)
		self.asistencia_resumen = self._formatear_resumen(
			detalle, len(faltas), minutos_tarde)
		if not silencioso:
			_logger.info(
				'Asistencias %s: %s días evaluados, %s faltas, %s min tarde',
				self.employee_id.name, len(detalle), len(faltas),
				minutos_tarde)
		return True

	def _conciliar_periodo(self, version_id, calendario_id):
		"""Devuelve el detalle por día laborable del periodo:
		[{fecha, estado: asistio|falta|justificado, minutos_tarde,
		  horas_esperadas, horas_marcadas}].  El estado por día se decide
		en _evaluar_dia (punto de extensión de la fase 2)."""
		zona = pytz.timezone(calendario_id.tz or 'America/Lima')
		horario = self._horario_semana(calendario_id)

		checadas_por_dia = {}
		asistencias = self.env['hr.attendance'].search([
			('employee_id', '=', self.employee_id.id),
			('check_in', '<', datetime.combine(
				self.date_to + timedelta(days=1), datetime.min.time())),
			('check_in', '>=', datetime.combine(
				self.date_from - timedelta(days=1), datetime.min.time())),
		])
		for checada_id in asistencias:
			entrada_local = pytz.utc.localize(
				checada_id.check_in).astimezone(zona)
			fecha = entrada_local.date()
			minutos = entrada_local.hour * 60 + entrada_local.minute
			previo = checadas_por_dia.get(fecha)
			horas = checada_id.worked_hours or 0.0
			if previo:
				previo['primer_ingreso'] = min(
					previo['primer_ingreso'], minutos)
				previo['horas'] += horas
			else:
				checadas_por_dia[fecha] = {
					'primer_ingreso': minutos, 'horas': horas}

		dias_justificados = self._dias_con_ausencia_aprobada()

		detalle = []
		fecha = self.date_from
		while fecha <= self.date_to:
			jornada = horario.get(fecha.weekday())
			if jornada:
				detalle.append(self._evaluar_dia(
					fecha, jornada,
					checadas_por_dia.get(fecha),
					fecha in dias_justificados))
			fecha += timedelta(days=1)
		return detalle

	def _evaluar_dia(self, fecha, jornada, checada, justificado):
		"""FASE 2: sobreescribir aquí para evaluación proporcional por
		horas (jornada trae horas_esperadas y hora de entrada; checada
		trae primer_ingreso y horas marcadas)."""
		compania_id = self.company_id
		valores = {
			'fecha': fecha,
			'horas_esperadas': jornada['horas'],
			'horas_marcadas': checada and checada['horas'] or 0.0,
			'minutos_tarde': 0,
		}
		if justificado:
			valores['estado'] = 'justificado'
		elif not checada:
			valores['estado'] = 'falta'
		else:
			valores['estado'] = 'asistio'
			retraso = (checada['primer_ingreso'] - jornada['entrada']
					   - compania_id.asistencia_tolerancia_minutos)
			valores['minutos_tarde'] = max(0, retraso)
			# FASE 2: horas no trabajadas del día como fracción de día.
			# Se resta lo ya cobrado como tardanza para no duplicar.
			if compania_id.asistencia_evaluar_horas:
				faltante = (valores['horas_esperadas']
							- valores['horas_marcadas']
							- valores['minutos_tarde'] / 60.0)
				if faltante > compania_id.asistencia_margen_horas:
					valores['estado'] = 'parcial'
					valores['horas_faltantes'] = round(faltante, 2)
		return valores

	# ------------------------------------------------------------------
	# Escritura en la boleta
	# ------------------------------------------------------------------
	def _tipo_entrada(self, xmlid):
		tipo_id = self.env.ref(xmlid, raise_if_not_found=False)
		if not tipo_id:
			raise UserError(_(
				'Falta el tipo de entrada de trabajo %s: actualice '
				'solse_pe_payroll_asistencia_ee.') % xmlid)
		return tipo_id

	def _escribir_linea_dias(self, codigo, xmlid_tipo, nombre, secuencia,
							 dias, horas):
		"""Una línea de días trabajados EE. Solo los campos que el modelo
		deja escribir: `code` es related a `work_entry_type_id.code`
		(hr_payslip_worked_days.py:17), `is_paid` compute desde la
		estructura (:21) y `version_id` related a la boleta (:23)."""
		lineas_previas = self.worked_days_line_ids.filtered(
			lambda l: l.code == codigo)
		if not dias:
			lineas_previas.unlink()
			return
		valores = {
			'name': nombre,
			'work_entry_type_id': self._tipo_entrada(xmlid_tipo).id,
			'sequence': secuencia,
			'number_of_days': dias,
			'number_of_hours': horas,
			'payslip_id': self.id,
		}
		if lineas_previas:
			lineas_previas[0].write(valores)
			(lineas_previas - lineas_previas[0]).unlink()
		else:
			self.env['hr.payslip.worked_days'].create(valores)

	def _escribir_faltas(self, version_id, cantidad):
		horas_dia = (version_id.resource_calendar_id.hours_per_day
					 or 8.0)
		self._escribir_linea_dias(
			CODIGO_FALTA,
			'solse_pe_payroll_asistencia_ee.work_entry_type_falta_pe',
			'Faltas (asistencias)', 30,
			cantidad, cantidad * horas_dia)

	def _escribir_faltas_parciales(self, version_id, horas_faltantes):
		horas_dia = (version_id.resource_calendar_id.hours_per_day or 8.0)
		self._escribir_linea_dias(
			CODIGO_FALTA_PARCIAL,
			'solse_pe_payroll_asistencia_ee.work_entry_type_falta_parcial_pe',
			'Horas no trabajadas (asistencias)', 31,
			round(horas_faltantes / horas_dia, 4) if horas_faltantes else 0.0,
			round(horas_faltantes, 2))

	def _escribir_tardanzas(self, minutos_tarde):
		# La conciliación es la fuente de verdad de tardanzas: si existe el
		# input MANUAL del núcleo (TARD_001, minutos) se retira para evitar
		# el doble descuento con TAR_001. Queda avisado en el resumen.
		manuales = self.input_line_ids.filtered(
			lambda l: l.code == 'TARD_001')
		if manuales:
			manuales.unlink()
			self._tardanza_manual_retirada = True
		inputs_previos = self.input_line_ids.filtered(
			lambda l: l.code == CODIGO_TARDANZA)
		descontar = self.company_id.asistencia_descontar_tardanzas
		horas = round(minutos_tarde / 60.0, 2)
		if not minutos_tarde or not descontar:
			inputs_previos.unlink()
			return
		tipo_id = self.env.ref(
			'solse_pe_payroll_asistencia_ee.input_type_tardanzas',
			raise_if_not_found=False)
		if not tipo_id:
			raise UserError(_(
				'Falta el tipo de entrada TARDANZAS: actualice '
				'solse_pe_payroll_asistencia_ee.'))
		# EE: `input_type_id` required y `code` related a él
		# (hr_payslip_input.py:17-19); `version_id` related a la boleta.
		valores = {
			'name': 'Horas de tardanza (asistencias)',
			'input_type_id': tipo_id.id,
			'amount': horas,
			'payslip_id': self.id,
		}
		if inputs_previos:
			inputs_previos[0].write(valores)
			(inputs_previos - inputs_previos[0]).unlink()
		else:
			self.env['hr.payslip.input'].create(valores)

	# ------------------------------------------------------------------
	# Utilitarios
	# ------------------------------------------------------------------
	@api.model
	def _horario_semana(self, calendario_id):
		"""{weekday: {'entrada': minutos, 'horas': horas_del_día}}"""
		horario = {}
		for franja_id in calendario_id.attendance_ids:
			# Las franjas de almuerzo (day_period='lunch') no son horas
			# exigibles: hr.attendance ya reporta las marcadas netas de
			# almuerzo, y sumarlas aquí creaba 1 h "faltante" fantasma
			# por día en la evaluación por horas.
			if franja_id.display_type or \
					getattr(franja_id, 'day_period', '') == 'lunch':
				continue
			dia = int(franja_id.dayofweek)
			entrada = int(franja_id.hour_from * 60)
			horas = max(0.0, franja_id.hour_to - franja_id.hour_from)
			if dia in horario:
				horario[dia]['entrada'] = min(
					horario[dia]['entrada'], entrada)
				horario[dia]['horas'] += horas
			else:
				horario[dia] = {'entrada': entrada, 'horas': horas}
		return horario

	def _dias_con_ausencia_aprobada(self):
		dias = set()
		ausencias = self.env['hr.leave'].search([
			('employee_id', '=', self.employee_id.id),
			('state', '=', 'validate'),
			('date_from', '<=', fields.Datetime.to_datetime(
				str(self.date_to)) + timedelta(days=1)),
			('date_to', '>=', fields.Datetime.to_datetime(
				str(self.date_from)))])
		for ausencia_id in ausencias:
			fecha = max(ausencia_id.date_from.date(), self.date_from)
			fin = min(ausencia_id.date_to.date(), self.date_to)
			while fecha <= fin:
				dias.add(fecha)
				fecha += timedelta(days=1)
		return dias

	def _formatear_resumen(self, detalle, faltas, minutos_tarde):
		lineas = [
			'Conciliación de asistencias — %s al %s' % (
				self.date_from, self.date_to),
		]
		if getattr(self, '_tardanza_manual_retirada', False):
			lineas.append('AVISO: se retiró el input manual de tardanzas '
						  '(TARD_001) — la conciliación es la fuente de '
						  'verdad de este concepto.')
		lineas += [
			'Días laborables evaluados: %s · Faltas: %s · '
			'Tardanza acumulada: %s min' % (
				len(detalle), faltas, minutos_tarde),
			'',
		]
		for dia in detalle:
			marca = {'asistio': '✔', 'falta': '✘ FALTA',
					 'parcial': '◐ parcial',
					 'justificado': '• justificado'}[dia['estado']]
			extra = (' · tarde %s min' % dia['minutos_tarde']
					 if dia['minutos_tarde'] else '')
			if dia.get('horas_faltantes'):
				extra += ' · faltan %.2f h' % dia['horas_faltantes']
			lineas.append('%s  %s%s' % (dia['fecha'], marca, extra))
		return '\n'.join(lineas)
