# -*- coding: utf-8 -*-

# Reparto de utilidades D.Leg. 892:
#   monto a repartir = renta neta anual × % según actividad (CIIU):
#   pesqueras/telecom/industriales 10% · mineras/comercio/restaurantes
#   8% · otras 5%.
#   50% en proporción a los DÍAS efectivamente laborados por cada
#   trabajador en el ejercicio, 50% en proporción a las REMUNERACIONES
#   percibidas. Tope individual: 18 remuneraciones mensuales.
# El wizard calcula la tabla, exporta Excel, y deja el importe listo
# para registrarse como input UTIL_001 en la boleta del mes de pago.

import base64
import io
from datetime import date

import xlsxwriter

from odoo import _, fields, models


class SolsePayrollUtilidadesWizard(models.TransientModel):
	_name = 'solse.payroll.utilidades.wizard'
	_description = 'Reparto de utilidades D.Leg. 892 (PE)'

	anio = fields.Integer(string='Ejercicio (año)', required=True,
						  default=lambda self: fields.Date.today().year - 1)
	renta_neta = fields.Float(string='Renta neta anual (base del reparto)',
							  required=True,
							  help='Renta neta del ejercicio antes de '
								   'impuestos, según la DJ anual.')
	porcentaje = fields.Selection([
		('0.10', '10% - Pesqueras / Telecomunicaciones / Industriales'),
		('0.08', '8% - Mineras / Comercio / Restaurantes'),
		('0.05', '5% - Otras actividades'),
	], string='Porcentaje según actividad (CIIU)', required=True)
	archivo = fields.Binary(string='Excel del reparto', readonly=True)
	archivo_nombre = fields.Char()
	resumen = fields.Text(readonly=True)

	def action_calcular(self):
		self.ensure_one()
		inicio = date(self.anio, 1, 1)
		fin = date(self.anio, 12, 31)
		estructuras = [self.env.ref(
			'solse_pe_payroll.hr_payroll_structure_%s' % s).id
			for s in ('mensual_empleados', 'semanal_obreros')]
		boletas = self.env['hr.payslip'].search([
			('state', 'in', ('validated', 'paid')),
			('struct_id', 'in', estructuras),
			('date_from', '>=', inicio), ('date_to', '<=', fin),
			('company_id', '=', self.env.company.id),
		])
		if not boletas:
			return {'type': 'ir.actions.client', 'tag': 'display_notification',
					'params': {'type': 'warning', 'title': _('Sin boletas'),
							   'message': _('No hay boletas validadas del '
											'ejercicio %s.') % self.anio}}
		datos = {}
		for boleta_id in boletas:
			fila = datos.setdefault(boleta_id.employee_id, {
				'dias': 0.0, 'remu': 0.0})
			for wd_id in boleta_id.worked_days_line_ids:
				if wd_id.is_paid:
					fila['dias'] += wd_id.number_of_days
			fila['remu'] += sum(boleta_id.line_ids.filtered(
				lambda l: l.code == 'GROSS').mapped('total'))
		monto = self.renta_neta * float(self.porcentaje)
		mitad = monto / 2.0
		total_dias = sum(f['dias'] for f in datos.values()) or 1.0
		total_remu = sum(f['remu'] for f in datos.values()) or 1.0
		filas = []
		for empleado_id, f in sorted(datos.items(), key=lambda x: x[0].name):
			por_dias = mitad * f['dias'] / total_dias
			por_remu = mitad * f['remu'] / total_remu
			bruto = por_dias + por_remu
			sueldo = empleado_id.version_id.wage or 0.0
			tope = sueldo * 18.0
			final = min(bruto, tope) if tope else bruto
			filas.append((empleado_id, f['dias'], f['remu'], por_dias,
						  por_remu, bruto, final))
		remanente = sum(x[5] - x[6] for x in filas)

		buffer = io.BytesIO()
		libro = xlsxwriter.Workbook(buffer, {'in_memory': True})
		hoja = libro.add_worksheet('Utilidades %s' % self.anio)
		f_cab = libro.add_format({'bold': True, 'bg_color': '#714B67',
								  'font_color': 'white', 'border': 1})
		f_num = libro.add_format({'num_format': '#,##0.00', 'border': 1})
		f_txt = libro.add_format({'border': 1})
		hoja.write_row(0, 0, ['Reparto de utilidades D.Leg. 892 - Ejercicio %s'
							  % self.anio])
		hoja.write_row(1, 0, ['Renta neta: %.2f · %%: %s · Monto a repartir: %.2f'
							  % (self.renta_neta, self.porcentaje, monto)])
		cabeceras = ['DNI', 'Trabajador', 'Días laborados', 'Remuneraciones',
					 '50% por días', '50% por remun.', 'Bruto',
					 'A pagar (tope 18 sueldos)']
		hoja.write_row(3, 0, cabeceras, f_cab)
		hoja.set_column(1, 1, 34)
		hoja.set_column(2, 7, 14)
		r = 4
		for empleado_id, dias, remu, pd, pr, bruto, final in filas:
			hoja.write(r, 0, empleado_id.identification_id or '', f_txt)
			hoja.write(r, 1, empleado_id.name, f_txt)
			for c, v in enumerate([dias, remu, pd, pr, bruto, final], start=2):
				hoja.write_number(r, c, round(v, 2), f_num)
			r += 1
		libro.close()
		self.archivo = base64.b64encode(buffer.getvalue())
		self.archivo_nombre = 'Utilidades_%s.xlsx' % self.anio
		self.resumen = _(
			'Monto repartido: %(m).2f · Trabajadores: %(n)s · '
			'Remanente por topes (va al ex-trabajador/Estado según norma): '
			'%(r).2f\nSiguiente paso: registrar el importe "A pagar" de cada '
			'trabajador como entrada "Participación de utilidades" (UTIL_001) '
			'en su boleta del mes de pago — grava renta de 5ta '
			'automáticamente.') % {'m': monto, 'n': len(filas), 'r': remanente}
		return {'type': 'ir.actions.act_window', 'res_model': self._name,
				'res_id': self.id, 'view_mode': 'form', 'target': 'new',
				'name': _('Reparto de utilidades')}
