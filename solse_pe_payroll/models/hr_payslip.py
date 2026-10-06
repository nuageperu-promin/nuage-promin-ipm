# -*- coding: utf-8 -*-

# Extensiones de nómina del núcleo PE:
# - hr.payslip: mes/año de nómina (convención peruana de mes de 30 días,
#   agrupación de semanales por mes de devengue).
# - hr.salary.rule: mapeo a conceptos PLAME (T22) y flags de uso.
# - hr.salary.rule.category: posición del concepto en la boleta de pago.

from odoo import api, fields, models


class HrPayslip(models.Model):
	_inherit = 'hr.payslip'

	date_start = fields.Char(
		string='Mes/Año nómina',
		compute='_compute_periodo_nomina',
		store=True,
		help='Periodo de devengue en formato MM/YYYY. Las nóminas semanales '
			 'se agrupan por el mes de su fecha de inicio.'
	)
	date_start_dt = fields.Date(
		string='Mes de nómina',
		compute='_compute_periodo_nomina',
		store=True,
	)

	def action_print_payslip(self):
		"""El botón "Imprimir" del recibo genera la Boleta de Pago formal
		peruana (D.S. 001-98-TR). El reporte nativo de Odoo queda
		disponible en el menú del engranaje."""
		return self.env.ref(
			'solse_pe_payroll.action_reporte_boleta_pago').report_action(self)

	@api.depends('date_from')
	def _compute_periodo_nomina(self):
		for boleta in self:
			if not boleta.date_from:
				boleta.date_start = False
				boleta.date_start_dt = False
				continue
			boleta.date_start = boleta.date_from.strftime('%m/%Y')
			boleta.date_start_dt = boleta.date_from.replace(day=1)

	# ------------------------------------------------------------- N-7
	# Días no pagados en días CALENDARIO, que es la unidad del mes comercial
	# de 30 (D.Leg. 713). Versión ENTERPRISE, escrita contra hr_payroll y
	# no copiada del shim de Community (lección de N-9):
	#
	# * `worked_days_line_ids` sale de las entradas de trabajo, que se
	#   generan sobre el calendario laboral del empleado
	#   (hr_payroll/models/hr_payslip.py:1436-1472): un goce del 1 al 30
	#   llega como 22 días. Restarlos de 30 mezcla unidades.
	#   MEDIDO en el caso NOMINA EE (2026-09-22, sueldo 3.000): Nilda
	#   800,00 donde la norma da 0,00; Óscar 1.900,00 donde da 1.500,00.
	# * Qué tipos NO se pagan lo declara la estructura en
	#   `unpaid_work_entry_type_ids`; el tipo de ausencia se sube desde ahí
	#   por `hr.leave.type.work_entry_type_id`.
	# * `payslip` en el localdict ES el registro (hr_payslip.py:1034), así
	#   que la regla podría llamar a un método; se expone como CAMPO igual
	#   que en Community para que las cuatro reglas lean lo mismo.
	pe_dias_no_pagados = fields.Float(
		string='Días no pagados (calendario)',
		compute='_compute_pe_dias_no_pagados',
		help='Días calendario de las ausencias no pagadas dentro del '
			 'periodo, más los días no pagados que no vienen de una '
			 'ausencia (faltas de asistencia). Es lo que RB_001 y RBS_002 '
			 'restan de la base de 30.')

	@api.depends('date_from', 'date_to', 'employee_id', 'struct_id',
				 'worked_days_line_ids.number_of_days',
				 'worked_days_line_ids.is_paid')
	def _compute_pe_dias_no_pagados(self):
		for boleta in self:
			boleta.pe_dias_no_pagados = boleta.pe_dias_no_pagados_comerciales()

	def pe_tipos_ausencia_no_pagada(self):
		"""Los `hr.leave.type` que esta boleta NO paga, según su estructura:
		los que apuntan a un tipo de entrada declarado en
		`unpaid_work_entry_type_ids` (hr_payroll/models/hr_payroll_structure.py:61)."""
		self.ensure_one()
		tipos_entrada = self.struct_id.unpaid_work_entry_type_ids
		if not tipos_entrada:
			return self.env['hr.leave.type']
		return self.env['hr.leave.type'].search([
			('work_entry_type_id', 'in', tipos_entrada.ids)])

	def pe_dias_no_pagados_comerciales(self):
		"""Días calendario de las ausencias no pagadas, recortadas al
		periodo (una ausencia a caballo entre dos meses descuenta en cada
		uno los días que le tocan), más las líneas no pagadas ajenas a
		esas ausencias (faltas y medias jornadas de asistencia), que se
		distinguen por el código del tipo de entrada para no contar dos
		veces la línea de la propia ausencia."""
		self.ensure_one()
		if not self.date_from or not self.date_to:
			return 0.0
		tipos = self.pe_tipos_ausencia_no_pagada()
		if not tipos or not self.employee_id:
			return self._pe_dias_no_pagados_de_las_lineas()
		ausencias = self.env['hr.leave'].search([
			('employee_id', '=', self.employee_id.id),
			('holiday_status_id', 'in', tipos.ids),
			('state', '=', 'validate'),
			('request_date_from', '<=', self.date_to),
			('request_date_to', '>=', self.date_from),
		])
		if not ausencias:
			# Días marcados como no pagados sin ausencia que los explique:
			# se vuelve al recuento por líneas antes que dejar de
			# descontar en silencio.
			return self._pe_dias_no_pagados_de_las_lineas()
		dias = 0.0
		for ausencia in ausencias:
			inicio = max(ausencia.request_date_from, self.date_from)
			fin = min(ausencia.request_date_to, self.date_to)
			if fin >= inicio:
				dias += (fin - inicio).days + 1
		return dias + self._pe_dias_no_pagados_ajenos_a_ausencias(tipos)

	def _pe_dias_no_pagados_ajenos_a_ausencias(self, tipos):
		self.ensure_one()
		codigos_de_ausencia = set(filter(
			None, tipos.mapped('work_entry_type_id.code')))
		return sum(abs(linea.number_of_days)
				   for linea in self.worked_days_line_ids
				   if not linea.is_paid
				   and linea.code not in codigos_de_ausencia)

	def _pe_dias_no_pagados_de_las_lineas(self):
		"""El recuento anterior a N-7, en días del calendario laboral.
		Salida de emergencia. `abs()` porque los reembolsos invierten el
		signo (hr_payslip.py:734-736)."""
		self.ensure_one()
		return sum(abs(linea.number_of_days)
				   for linea in self.worked_days_line_ids
				   if not linea.is_paid)


class HrSalaryRuleCategory(models.Model):
	_inherit = 'hr.salary.rule.category'

	invoice_position = fields.Selection(
		string='Posición en boleta',
		selection=[
			('pos_1', '1 - Ingresos'),
			('pos_2', '2 - Descuentos'),
			('pos_3', '3 - Aportes del empleador'),
		],
		default='pos_1',
		help='Columna de la boleta de pago en la que se imprimen los '
			 'conceptos de esta categoría.'
	)


class HrSalaryRule(models.Model):
	_inherit = 'hr.salary.rule'

	plame_ids = fields.Many2many(
		comodel_name='plame.lines',
		string='Conceptos PLAME (T22)',
		help='Conceptos de la tabla 22 a los que tributa el resultado de '
			 'esta regla en la declaración PLAME.'
	)
	utilities = fields.Boolean(
		string='¿Aplica para utilidades?',
		help='El resultado de esta regla forma parte de la base de cálculo '
			 'de la participación en utilidades (D.Leg. 892).'
	)
	apply_advance_payroll = fields.Boolean(
		string='¿Aplica en nómina de adelanto?',
	)
