# -*- coding: utf-8 -*-

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

# Estructuras que descuentan faltas al treintavo. Gratificaciones, CTS,
# vacaciones y liquidación no llevan días trabajados que descontar.
ESTRUCTURAS_CON_FALTAS = [
	'solse_pe_payroll.hr_payroll_structure_mensual_empleados',
	'solse_pe_payroll.hr_payroll_structure_semanal_obreros',
]
# La base recibe el input para que `replicar_reglas_base` lo vea junto a
# TAR_001; las dos de arriba, para que el desplegable de la boleta lo
# ofrezca (`hr.payslip.input.input_type_id` filtra por
# `struct_id.input_line_type_ids`, hr_payslip_input.py:17-18).
ESTRUCTURAS_CON_TARDANZAS = [
	'solse_pe_payroll.hr_payroll_structure_base',
] + ESTRUCTURAS_CON_FALTAS


class SolsePayrollInicializador(models.AbstractModel):
	_inherit = 'solse.payroll.inicializador'

	@api.model
	def configurar_asistencia_ee(self):
		"""Declara FALTA y FALTA_PARCIAL como tipos NO pagados y publica el
		input TARDANZAS en las estructuras.

		Es lo que en Enterprise hace que la línea de falta no se pague:
		`hr.payslip.worked_days.is_paid` se calcula desde
		`struct.unpaid_work_entry_type_ids`
		(`hr_payroll/models/hr_payslip_worked_days.py:32-35`). Mismo
		mecanismo que usa `configurar_vacaciones_no_pagadas` para
		VACPE100.

		Idempotente y sin escritura cuando ya está: se llama en cada
		actualización desde el `<function>` del data.
		"""
		tipos = self.env['hr.work.entry.type']
		for xmlid in ('solse_pe_payroll_asistencia_ee.work_entry_type_falta_pe',
					  'solse_pe_payroll_asistencia_ee.work_entry_type_falta_parcial_pe'):
			tipo_id = self.env.ref(xmlid, raise_if_not_found=False)
			if tipo_id:
				tipos |= tipo_id
		for xmlid in ESTRUCTURAS_CON_FALTAS:
			estructura_id = self.env.ref(xmlid, raise_if_not_found=False)
			if not estructura_id:
				continue
			faltantes = tipos - estructura_id.unpaid_work_entry_type_ids
			if faltantes:
				estructura_id.unpaid_work_entry_type_ids = [
					(4, tipo_id.id) for tipo_id in faltantes]
				_logger.info('Asistencias EE: %s tipo(s) de falta declarados '
							 'no pagados en "%s".', len(faltantes),
							 estructura_id.name)

		input_id = self.env.ref(
			'solse_pe_payroll_asistencia_ee.input_type_tardanzas',
			raise_if_not_found=False)
		if not input_id:
			return
		for xmlid in ESTRUCTURAS_CON_TARDANZAS:
			estructura_id = self.env.ref(xmlid, raise_if_not_found=False)
			if estructura_id and input_id not in estructura_id.input_line_type_ids:
				estructura_id.input_line_type_ids = [(4, input_id.id)]
