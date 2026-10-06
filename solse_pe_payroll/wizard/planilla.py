# -*- coding: utf-8 -*-

# Planilla de sueldos del mes: resumen multi-empleado de las boletas
# VALIDADAS/PAGADAS de las estructuras mensual y semanal (las semanales
# se agregan por empleado). PDF apaisado para firma + Excel para trabajo.

import base64
import io
from datetime import date

import xlsxwriter

from odoo import _, api, fields, models

MESES = [(str(m), n) for m, n in enumerate(
	['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio',
	 'Agosto', 'Setiembre', 'Octubre', 'Noviembre', 'Diciembre'], start=1)]

# (clave, etiqueta, códigos que suman)  — 'otros_*' se calculan por diferencia
COLUMNAS = [
	('rb', 'Rem. básica', ['RB_001', 'RBS_002']),
	('asf', 'Asig. fam.', ['ASF_001']),
	('hhee', 'HH.EE.', ['HE25_001', 'HE35_001']),
	('otros_ing', 'Otros ingresos', None),
	('total_ing', 'Total ingresos', ['GROSS']),
	('onp', 'ONP', ['ONP_001']),
	('afp', 'AFP', ['AFP_APO_001', 'AFP_COM_001', 'AFP_PRI_001']),
	('r5ta', 'Renta 5ta', ['R5TA_001']),
	('otros_desc', 'Otros dsctos.', None),
	('total_desc', 'Total dsctos.', None),
	('neto', 'Neto a pagar', ['NET']),
	('essalud', 'ESSALUD', ['ESSALUD_001', 'EPS_CRED_001']),
	('otros_aportes', 'Otros aportes', ['EPS_APO_001', 'SCTR_SAL_001',
									   'SCTR_PEN_001', 'SENATI_001']),
]


class SolsePayrollPlanillaWizard(models.TransientModel):
	_name = 'solse.payroll.planilla.wizard'
	_description = 'Planilla de sueldos del mes (PE)'

	mes = fields.Selection(selection=MESES, string='Mes', required=True,
						   default=lambda self: str(fields.Date.today().month))
	anio = fields.Integer(string='Año', required=True,
						  default=lambda self: fields.Date.today().year)
	incluir_semanales = fields.Boolean(string='Incluir nómina semanal (obreros)',
									   default=True)
	archivo = fields.Binary(string='Excel generado', readonly=True)
	archivo_nombre = fields.Char()

	# ------------------------------------------------------------------
	def _boletas(self):
		self.ensure_one()
		estructuras = [self.env.ref(
			'solse_pe_payroll.hr_payroll_structure_mensual_empleados').id]
		if self.incluir_semanales:
			estructuras.append(self.env.ref(
				'solse_pe_payroll.hr_payroll_structure_semanal_obreros').id)
		return self.env['hr.payslip'].search([
			('state', 'in', ('validated', 'paid')),
			('struct_id', 'in', estructuras),
			('date_start_dt', '=', date(self.anio, int(self.mes), 1)),
			('company_id', '=', self.env.company.id),
		])

	def obtener_datos(self):
		"""Filas por empleado (semanales agregadas) + fila de totales."""
		self.ensure_one()
		boletas = self._boletas()
		filas = {}
		for boleta_id in boletas:
			empleado_id = boleta_id.employee_id
			fila = filas.setdefault(empleado_id.id, {
				'dni': empleado_id.identification_id or '',
				'nombre': empleado_id.name,
				**{clave: 0.0 for clave, _e, _c in COLUMNAS},
			})
			totales_linea = {}
			for linea_id in boleta_id.line_ids:
				totales_linea[linea_id.code] = \
					totales_linea.get(linea_id.code, 0.0) + linea_id.total
			for clave, _etiqueta, codigos in COLUMNAS:
				if codigos:
					fila[clave] += sum(totales_linea.get(c, 0.0) for c in codigos)
		# Derivadas por diferencia y totales generales
		totales = {clave: 0.0 for clave, _e, _c in COLUMNAS}
		lista = sorted(filas.values(), key=lambda f: f['nombre'])
		for fila in lista:
			fila['total_desc'] = fila['total_ing'] - fila['neto']
			fila['otros_ing'] = fila['total_ing'] - fila['rb'] - fila['asf'] - fila['hhee']
			fila['otros_desc'] = (fila['total_desc'] - fila['onp']
								  - fila['afp'] - fila['r5ta'])
			for clave in totales:
				totales[clave] += fila[clave]
		return lista, totales

	def _nombre_periodo(self):
		return '%s %s' % (dict(MESES)[self.mes], self.anio)

	# ------------------------------------------------------------------
	def action_pdf(self):
		self.ensure_one()
		if not self._boletas():
			return self._sin_datos()
		return self.env.ref(
			'solse_pe_payroll.action_reporte_planilla').report_action(self)

	def action_excel(self):
		self.ensure_one()
		filas, totales = self.obtener_datos()
		if not filas:
			return self._sin_datos()
		buffer = io.BytesIO()
		libro = xlsxwriter.Workbook(buffer, {'in_memory': True})
		hoja = libro.add_worksheet('Planilla')
		f_titulo = libro.add_format({'bold': True, 'font_size': 13})
		f_cab = libro.add_format({'bold': True, 'bg_color': '#714B67',
								  'font_color': 'white', 'border': 1,
								  'text_wrap': True, 'valign': 'vcenter'})
		f_num = libro.add_format({'num_format': '#,##0.00', 'border': 1})
		f_txt = libro.add_format({'border': 1})
		f_tot = libro.add_format({'bold': True, 'num_format': '#,##0.00',
								  'border': 1, 'bg_color': '#F0E9EE'})
		hoja.write(0, 0, 'PLANILLA DE SUELDOS — %s' % self._nombre_periodo(), f_titulo)
		hoja.write(1, 0, '%s — RUC %s' % (self.env.company.name,
										  self.env.company.vat or ''))
		fila_cab = 3
		hoja.write(fila_cab, 0, 'DNI', f_cab)
		hoja.write(fila_cab, 1, 'Apellidos y nombres', f_cab)
		for col, (_clave, etiqueta, _c) in enumerate(COLUMNAS, start=2):
			hoja.write(fila_cab, col, etiqueta, f_cab)
		hoja.set_column(0, 0, 11)
		hoja.set_column(1, 1, 34)
		hoja.set_column(2, 1 + len(COLUMNAS), 12)
		r = fila_cab + 1
		for fila in filas:
			hoja.write(r, 0, fila['dni'], f_txt)
			hoja.write(r, 1, fila['nombre'], f_txt)
			for col, (clave, _e, _c) in enumerate(COLUMNAS, start=2):
				hoja.write_number(r, col, round(fila[clave], 2), f_num)
			r += 1
		hoja.write(r, 1, 'TOTALES', f_tot)
		hoja.write(r, 0, '', f_tot)
		for col, (clave, _e, _c) in enumerate(COLUMNAS, start=2):
			hoja.write_number(r, col, round(totales[clave], 2), f_tot)
		libro.close()
		self.archivo = base64.b64encode(buffer.getvalue())
		self.archivo_nombre = 'Planilla_%s_%s.xlsx' % (self.anio, self.mes.zfill(2))
		return {
			'type': 'ir.actions.act_window',
			'res_model': self._name,
			'res_id': self.id,
			'view_mode': 'form',
			'target': 'new',
			'name': _('Planilla de sueldos'),
		}

	def _sin_datos(self):
		return {
			'type': 'ir.actions.client',
			'tag': 'display_notification',
			'params': {
				'type': 'warning',
				'title': _('Sin boletas'),
				'message': _('No hay boletas validadas de %s.') % self._nombre_periodo(),
			},
		}
