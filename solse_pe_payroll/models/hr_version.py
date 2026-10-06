# -*- coding: utf-8 -*-

# En Odoo 19 el modelo hr.contract fue absorbido por hr.version.
# Aquí viven todos los campos contractuales de la localización peruana
# (antes en el _inherit de hr.contract del módulo v17).

from odoo import fields, models


class HrVersion(models.Model):
	_inherit = 'hr.version'

	labor_regime_id = fields.Many2one(
		comodel_name='employee.regime',
		string='Régimen Laboral',
		groups='hr_payroll.group_hr_payroll_user',
		tracking=True,
		help='Régimen laboral T33. Su clave de cálculo (general/pequeña/micro/agrario) '
			 'determina factores de gratificación, CTS y vacaciones en las reglas.'
	)
	labor_condition_id = fields.Many2one(
		comodel_name='type.contract',
		string='Condición laboral',
		groups='hr_payroll.group_hr_payroll_user',
	)
	work_occupation_id = fields.Many2one(
		comodel_name='work.occupation',
		string='Ocupación de trabajo',
		groups='hr_payroll.group_hr_payroll_user',
	)
	mintra_contract_id = fields.Many2one(
		comodel_name='mintra.contract',
		string='Tipo de contrato (MINTRA)',
		groups='hr_payroll.group_hr_payroll_user',
	)
	reason_low_id = fields.Many2one(
		comodel_name='low.reason',
		string='Motivo de baja',
		groups='hr_payroll.group_hr_payroll_user',
	)
	special_situation_id = fields.Many2one(
		comodel_name='special.situation',
		string='Situación especial',
		groups='hr_payroll.group_hr_payroll_user',
	)
	payment_type_id = fields.Many2one(
		comodel_name='payment.type',
		string='Tipo de pago',
		groups='hr_payroll.group_hr_payroll_user',
	)
	variable_payment_id = fields.Many2one(
		comodel_name='variable.payment',
		string='Remuneración variable',
		groups='hr_payroll.group_hr_payroll_user',
	)
	maximum_working_day = fields.Boolean(
		string='Jornada de trabajo máxima',
		groups='hr_payroll.group_hr_payroll_user',
	)
	atypical_cumulative_day = fields.Boolean(
		string='Jornada atípica o acumulativa',
		groups='hr_payroll.group_hr_payroll_user',
	)
	nocturnal_schedule = fields.Boolean(
		string='Trabajo en horario nocturno',
		groups='hr_payroll.group_hr_payroll_user',
		help='Si está activo, las reglas validan la sobretasa nocturna del 35% sobre la RMV.'
	)
	unionized = fields.Boolean(
		string='Sindicalizado',
		groups='hr_payroll.group_hr_payroll_user',
	)
	is_practitioner = fields.Boolean(
		string='¿Es practicante?',
		groups='hr_payroll.group_hr_payroll_user',
		help='Modalidades formativas (D.Leg. 1401 / Ley 28518). El soporte de cálculo '
			 'de subvenciones queda para una fase posterior; el flag se registra desde ya '
			 'para el T-Registro.'
	)
	compensation_in_kind = fields.Boolean(
		string='Remuneración en especie',
		groups='hr_payroll.group_hr_payroll_user',
	)
	advance_percent = fields.Float(
		string='Porcentaje de adelanto',
		groups='hr_payroll.group_hr_payroll_user',
		help='Porcentaje del básico que se paga en la nómina quincenal de adelanto.'
	)
	hiden_overtime = fields.Boolean(
		string='No mostrar horas extras en boleta',
		groups='hr_payroll.group_hr_payroll_user',
	)
