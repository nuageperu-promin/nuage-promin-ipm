# -*- coding: utf-8 -*-

# Planilla previsional AFPnet: Excel de importación (hoja TRABAJADOR,
# 17 columnas sin cabecera, formato del portal AFPnet), portado del v17.
# Solo trabajadores del SPP (con CUSPP). La remuneración asegurable es
# la base afecta (INA) de las boletas validadas del periodo.

import base64
import io
from datetime import date

import xlsxwriter

from odoo import _, fields, models

MESES = [(str(m), n) for m, n in enumerate(
	['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio',
	 'Agosto', 'Setiembre', 'Octubre', 'Noviembre', 'Diciembre'], start=1)]


class SolsePayrollAfpnetWizard(models.TransientModel):
	_name = 'solse.payroll.afpnet.wizard'
	_description = 'AFPnet - Planilla previsional (PE)'

	mes = fields.Selection(selection=MESES, string='Mes', required=True,
						   default=lambda self: str(fields.Date.today().month))
	anio = fields.Integer(string='Año', required=True,
						  default=lambda self: fields.Date.today().year)
	archivo = fields.Binary(string='Excel AFPnet', readonly=True)
	archivo_nombre = fields.Char()
	resumen = fields.Text(readonly=True)

	def action_generar(self):
		self.ensure_one()
		ref = self.env.ref
		estructuras = [ref('solse_pe_payroll.hr_payroll_structure_%s' % s).id
					   for s in ('mensual_empleados', 'semanal_obreros',
								 'vacaciones', 'liquidacion')
					   if ref('solse_pe_payroll.hr_payroll_structure_%s' % s,
							  raise_if_not_found=False)]
		periodo = date(self.anio, int(self.mes), 1)
		boletas = self.env['hr.payslip'].search([
			('state', 'in', ('validated', 'paid')),
			('struct_id', 'in', estructuras),
			('date_start_dt', '=', periodo),
			('company_id', '=', self.env.company.id),
			('employee_id.is_cuspp', '=', True),
		])
		if not boletas:
			return {'type': 'ir.actions.client', 'tag': 'display_notification',
					'params': {'type': 'warning', 'title': _('Sin datos'),
							   'message': _('No hay boletas validadas de '
											'trabajadores SPP en el periodo.')}}
		categoria_ina = ref('solse_pe_payroll.hr_salary_rule_category_ina_001')
		filas = []
		for empleado_id in boletas.mapped('employee_id').sorted('name'):
			propias = boletas.filtered(lambda b: b.employee_id == empleado_id)
			asegurable = sum(propias.line_ids.filtered(
				lambda l: l.category_id == categoria_ina).mapped('total'))
			version_id = empleado_id.version_id
			inicio = 'S' if (version_id.contract_date_start
							 and version_id.contract_date_start.year == self.anio
							 and version_id.contract_date_start.month == int(self.mes)) else 'N'
			fin = 'S' if (version_id.contract_date_end
						  and version_id.contract_date_end.year == self.anio
						  and version_id.contract_date_end.month == int(self.mes)) else 'N'
			filas.append([
				empleado_id.cuspp or '0',
				'0',  # tipo doc AFPnet: 0 = DNI (v1)
				empleado_id.identification_id or '',
				empleado_id.lastname or '',
				empleado_id.secondname or '',
				empleado_id.firstname or '',
				'S', inicio, fin,
				'L' if asegurable <= 0.005 else '',
				round(asegurable, 2),
				0, 0, 0, 'N', '',
			])
		buffer = io.BytesIO()
		libro = xlsxwriter.Workbook(buffer, {'in_memory': True})
		hoja = libro.add_worksheet('TRABAJADOR')
		formato = libro.add_format({'size': 10})
		hoja.set_column('B:Q', 15)
		for r, fila in enumerate(filas):
			hoja.write(r, 0, r + 1, formato)
			for c, valor in enumerate(fila, start=1):
				hoja.write(r, c, valor, formato)
		libro.close()
		self.archivo = base64.b64encode(buffer.getvalue())
		self.archivo_nombre = 'AFPNET_%s_%02d.xlsx' % (self.anio, int(self.mes))
		self.resumen = _('Trabajadores SPP incluidos: %s') % len(filas)
		return {'type': 'ir.actions.act_window', 'res_model': self._name,
				'res_id': self.id, 'view_mode': 'form', 'target': 'new',
				'name': _('AFPnet')}
