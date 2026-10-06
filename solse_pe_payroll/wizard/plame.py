# -*- coding: utf-8 -*-

# Generador de archivos de importación al PDT PLAME (estructura oficial
# de importación, vigente desde PLAME v2.x y sin cambios en 4.6):
#
#   0601{AAAAMM}{RUC}.rem  Ingresos y descuentos por trabajador y
#                          concepto T22: tipo_doc|nro_doc|concepto|
#                          devengado|pagado|
#   0601{AAAAMM}{RUC}.jor  Jornada: tipo_doc|nro_doc|dias_efectivos|
#                          horas_ord|min_ord|horas_extra|min_extra|
#   0601{AAAAMM}{RUC}.snl  Suspensiones/días subsidiados y no laborados:
#                          tipo_doc|nro_doc|tipo_suspension|dias|
#                          (v1: vacío — suspensiones aún no gestionadas)
#
# Reglas de armado:
# - Boletas VALIDADAS/PAGADAS del periodo (mensual, semanal agregada,
#   gratificaciones, vacaciones y liquidación).
# - Solo conceptos T22 declarables por el empleador (series 01xx-05xx,
#   07xx y 09xx): las aportaciones (06xx del trabajador y 08xx del
#   empleador) las CALCULA el propio PDT y no se importan.
# - Devengado = pagado (el flujo SOLSE valida y paga en el periodo).
# - Tipo de documento T3: DNI = 01.

import base64
import io
import zipfile
from datetime import date

from odoo import _, fields, models

MESES = [(str(m), n) for m, n in enumerate(
	['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio',
	 'Agosto', 'Setiembre', 'Octubre', 'Noviembre', 'Diciembre'], start=1)]


class SolsePayrollPlameWizard(models.TransientModel):
	_name = 'solse.payroll.plame.wizard'
	_description = 'PLAME - Archivos de importación al PDT (PE)'

	mes = fields.Selection(selection=MESES, string='Mes', required=True,
						   default=lambda self: str(fields.Date.today().month))
	anio = fields.Integer(string='Año', required=True,
						  default=lambda self: fields.Date.today().year)
	archivo = fields.Binary(string='ZIP PLAME', readonly=True)
	archivo_nombre = fields.Char()
	resumen = fields.Text(string='Resumen', readonly=True)

	# ------------------------------------------------------------------
	def _boletas(self):
		self.ensure_one()
		claves = ['hr_payroll_structure_mensual_empleados',
				  'hr_payroll_structure_semanal_obreros',
				  'hr_payroll_structure_gratificaciones',
				  'hr_payroll_structure_vacaciones',
				  'hr_payroll_structure_liquidacion']
		estructuras = []
		for clave in claves:
			registro_id = self.env.ref('solse_pe_payroll.' + clave,
									   raise_if_not_found=False)
			if registro_id:
				estructuras.append(registro_id.id)
		return self.env['hr.payslip'].search([
			('state', 'in', ('validated', 'paid')),
			('struct_id', 'in', estructuras),
			('date_start_dt', '=', date(self.anio, int(self.mes), 1)),
			('company_id', '=', self.env.company.id),
		])

	@staticmethod
	def _doc(empleado_id):
		# T3: 01 = DNI (v1: la matriz demo y el cliente usan DNI; carné de
		# extranjería y otros se incorporan con el campo de tipo de doc).
		return '01', (empleado_id.identification_id or '').strip()

	def action_generar(self):
		self.ensure_one()
		boletas = self._boletas()
		if not boletas:
			return {
				'type': 'ir.actions.client',
				'tag': 'display_notification',
				'params': {'type': 'warning', 'title': _('Sin boletas'),
						   'message': _('No hay boletas validadas del periodo.')},
			}

		# ---------- .rem: acumular por (empleado, concepto T22) ----------
		acumulado = {}          # (doc, codigo) -> monto
		empleados = {}          # doc -> employee record
		for boleta_id in boletas:
			tipo, numero = self._doc(boleta_id.employee_id)
			empleados[numero] = boleta_id.employee_id
			for linea_id in boleta_id.line_ids:
				if abs(linea_id.total) < 0.005:
					continue
				for concepto_id in linea_id.salary_rule_id.plame_ids:
					codigo = concepto_id.code
					# Aportaciones 06xx/08xx: las calcula el PDT según el
					# T-Registro. EXCEPCIÓN: 0605 (retención de renta de
					# 5ta) la declara el empleador y SÍ se exporta.
					if codigo[:2] == '08' or (codigo[:2] == '06' and codigo != '0605'):
						continue
					clave = (tipo, numero, codigo)
					acumulado[clave] = acumulado.get(clave, 0.0) + linea_id.total

		lineas_rem = []
		for (tipo, numero, codigo) in sorted(acumulado):
			monto = acumulado[(tipo, numero, codigo)]
			if abs(monto) < 0.005:
				continue
			lineas_rem.append('%s|%s|%s|%.2f|%.2f|' % (
				tipo, numero, codigo, monto, monto))

		# ---------- .jor: jornada por empleado ----------
		jornada = {}            # numero -> [dias, horas, he_horas_float]
		for boleta_id in boletas:
			# La jornada se reporta desde las planillas regulares
			if boleta_id.struct_id not in (
				self.env.ref('solse_pe_payroll.hr_payroll_structure_mensual_empleados'),
				self.env.ref('solse_pe_payroll.hr_payroll_structure_semanal_obreros'),
			):
				continue
			tipo, numero = self._doc(boleta_id.employee_id)
			datos = jornada.setdefault(numero, [tipo, 0.0, 0.0, 0.0])
			for wd_id in boleta_id.worked_days_line_ids:
				if wd_id.is_paid:
					datos[1] += wd_id.number_of_days
					datos[2] += wd_id.number_of_hours
			for input_id in boleta_id.input_line_ids:
				if input_id.code in ('HE25_001', 'HE35_001'):
					datos[3] += input_id.amount

		lineas_jor = []
		for numero in sorted(jornada):
			tipo, dias, horas, he = jornada[numero]
			# N-2b · Confirmado por la contadora (2026-09-22, P-02): el campo
			# que sigue a las horas ordinarias son los MINUTOS ordinarios.
			# Hasta 19.0.0.44 iba un 0 fijo y las horas se redondeaban, así
			# que una jornada de 7,5 h/día se declaraba como 8 h. Misma
			# descomposición que ya se hacía con las horas extra.
			horas_h = int(horas)
			horas_m = int(round((horas - horas_h) * 60))
			if horas_m == 60:
				horas_h, horas_m = horas_h + 1, 0
			he_h = int(he)
			he_m = int(round((he - he_h) * 60))
			if he_m == 60:
				he_h, he_m = he_h + 1, 0
			lineas_jor.append('%s|%s|%d|%d|%d|%d|%d|' % (
				tipo, numero, int(round(dias)), horas_h, horas_m, he_h, he_m))

		# ---------- .snl: suspensiones (v1 vacío) ----------
		contenido_snl = ''

		# ---------- empaquetar ----------
		ruc = ''.join(c for c in (self.env.company.vat or '') if c.isdigit())
		base = '0601%s%02d%s' % (self.anio, int(self.mes), ruc)
		buffer = io.BytesIO()
		with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
			zf.writestr(base + '.rem', '\r\n'.join(lineas_rem) + ('\r\n' if lineas_rem else ''))
			zf.writestr(base + '.jor', '\r\n'.join(lineas_jor) + ('\r\n' if lineas_jor else ''))
			zf.writestr(base + '.snl', contenido_snl)
		self.archivo = base64.b64encode(buffer.getvalue())
		self.archivo_nombre = 'PLAME_%s.zip' % base
		conceptos = sorted({c for (_t, _n, c) in acumulado})
		self.resumen = (
			'Boletas del periodo: %s\nTrabajadores en .rem: %s\n'
			'Líneas .rem: %s | Líneas .jor: %s\nConceptos T22: %s'
		) % (len(boletas), len(empleados), len(lineas_rem), len(lineas_jor),
			 ', '.join(conceptos))
		return {
			'type': 'ir.actions.act_window',
			'res_model': self._name,
			'res_id': self.id,
			'view_mode': 'form',
			'target': 'new',
			'name': _('PLAME - Archivos PDT'),
		}
