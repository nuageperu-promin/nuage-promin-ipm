# -*- coding: utf-8 -*-

# Datos del trabajador exigidos por T-Registro (RM 170-2023-TR) y PLAME.
# Los campos genéricos fields_1..4_* del módulo v17 fueron reemplazados por
# payroll_properties nativo de hr.version (valores por empleado definidos
# en la estructura salarial).

from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models


class HrEmployee(models.Model):
	_inherit = 'hr.employee'

	# ------------------------------------------------------------------
	# Identificación y nombres (T-Registro exige apellidos separados)
	# ------------------------------------------------------------------
	firstname = fields.Char(string='Nombres', groups='hr.group_hr_user')
	lastname = fields.Char(string='Apellido paterno', groups='hr.group_hr_user')
	secondname = fields.Char(string='Apellido materno', groups='hr.group_hr_user')
	academic_degree_id = fields.Many2one(
		comodel_name='academic.degree',
		string='Situación educativa',
		groups='hr.group_hr_user',
	)
	disability = fields.Boolean(
		string='Discapacidad',
		groups='hr.group_hr_user',
		help='Trabajador con discapacidad acreditada (CONADIS).'
	)

	# ------------------------------------------------------------------
	# Sistema pensionario
	# ------------------------------------------------------------------
	pension_system_id = fields.Many2one(
		comodel_name='pension.system',
		string='Sistema pensionario',
		groups='hr.group_hr_user',
		tracking=True,
	)
	cuspp = fields.Char(string='CUSPP', groups='hr.group_hr_user')
	is_cuspp = fields.Boolean(
		string='Requiere CUSPP',
		related='pension_system_id.cuspp',
	)
	no_provide_pension = fields.Boolean(
		string='No aporta pensión',
		groups='hr.group_hr_user',
		help='Casos excepcionales sin aporte pensionario (p. ej. pensionista que retorna).'
	)
	no_apply_afp_premium = fields.Boolean(
		string='No aplica prima de seguro AFP',
		groups='hr.group_hr_user',
		help='Afiliados que superan la edad de cobertura del seguro de invalidez y sobrevivencia.'
	)
	commission_type = fields.Selection(
		selection=[('flow', 'Comisión por flujo'), ('mixed', 'Comisión mixta')],
		string='Tipo de comisión AFP',
		default='flow',
		groups='hr.group_hr_user',
	)

	# ------------------------------------------------------------------
	# Salud: régimen, EPS y derechohabientes
	# ------------------------------------------------------------------
	health_regime_id = fields.Many2one(
		comodel_name='health.regime',
		string='Régimen de salud',
		groups='hr.group_hr_user',
	)
	management_eps = fields.Many2one(
		comodel_name='eps.management',
		string='Plan EPS',
		groups='hr.group_hr_user',
	)
	relative_ids = fields.One2many(
		comodel_name='hr.employee.relative',
		inverse_name='employee_id',
		string='Derechohabientes',
		groups='hr.group_hr_user',
	)

	# ------------------------------------------------------------------
	# Seguros
	# ------------------------------------------------------------------
	life_insurance_id = fields.Many2one(
		comodel_name='life.insurance',
		string='Vida Ley',
		groups='hr.group_hr_user',
	)
	pension_sctr = fields.Boolean(
		string='SCTR Pensión',
		groups='hr.group_hr_user',
		help='Trabajador cubierto por SCTR (actividad de riesgo, Anexo 5 D.S. 009-97-SA).'
	)

	# ------------------------------------------------------------------
	# Cuentas bancarias de sueldo y CTS
	# El detalle de cuentas vive en res.partner.bank (extendido abajo);
	# estos computados exponen los datos en la ficha para reportes/boleta.
	# ------------------------------------------------------------------
	account_salary_bank = fields.Char(
		string='Cuenta sueldo', readonly=True, compute='_compute_cuentas_bancarias')
	type_salary_bank = fields.Char(
		string='Banco sueldo', readonly=True, compute='_compute_cuentas_bancarias')
	account_cts_bank = fields.Char(
		string='Cuenta CTS', readonly=True, compute='_compute_cuentas_bancarias')
	type_cts_bank = fields.Char(
		string='Banco CTS', readonly=True, compute='_compute_cuentas_bancarias')

	# ------------------------------------------------------------------
	# Descuentos judiciales
	# ------------------------------------------------------------------
	judicial_discount = fields.Float(
		string='Descuento judicial (importe)',
		groups='hr_payroll.group_hr_payroll_user',
	)
	judicial_discount_percent = fields.Float(
		string='Descuento judicial (%)',
		groups='hr_payroll.group_hr_payroll_user',
	)
	exists_beneficiary = fields.Boolean(
		string='¿Tiene beneficiario?',
		groups='hr_payroll.group_hr_payroll_user',
	)
	beneficiary = fields.Many2one(
		comodel_name='res.partner',
		string='Beneficiario',
		groups='hr_payroll.group_hr_payroll_user',
		help='Beneficiario del descuento por mandato judicial (alimentos u otros).'
	)

	# ------------------------------------------------------------------
	# Otros
	# ------------------------------------------------------------------
	age = fields.Float(string='Edad', compute='_compute_age', groups='hr.group_hr_user')
	is_employer = fields.Boolean(
		string='Firma como empleador',
		groups='hr.group_hr_user',
		help='Empleado cuya firma aparece como representante del empleador en las boletas.'
	)
	employer_sign = fields.Image(string='Firma del empleador', groups='hr.group_hr_user')

	@api.depends('birthday')
	def _compute_age(self):
		for empleado in self:
			if not empleado.birthday:
				empleado.age = 0
				continue
			edad = relativedelta(datetime.now(), empleado.birthday)
			empleado.age = edad.years + (edad.months / 12)

	@api.depends('bank_account_ids', 'bank_account_ids.uso_cuenta',
				 'bank_account_ids.acc_number', 'bank_account_ids.bank_id')
	def _compute_cuentas_bancarias(self):
		for empleado in self:
			cuentas = empleado.sudo().bank_account_ids
			cuenta_sueldo = cuentas.filtered(lambda c: c.uso_cuenta == 'sueldo')[:1]
			cuenta_cts = cuentas.filtered(lambda c: c.uso_cuenta == 'cts')[:1]
			empleado.account_salary_bank = cuenta_sueldo.acc_number or ''
			empleado.type_salary_bank = cuenta_sueldo.bank_id.name or ''
			empleado.account_cts_bank = cuenta_cts.acc_number or ''
			empleado.type_cts_bank = cuenta_cts.bank_id.name or ''


class ResPartnerBank(models.Model):
	_inherit = 'res.partner.bank'

	uso_cuenta = fields.Selection(
		selection=[
			('sueldo', 'Cuenta sueldo'),
			('cts', 'Cuenta CTS'),
			('otra', 'Otra'),
		],
		string='Uso de la cuenta',
		default='sueldo',
		help='Determina qué cuenta usa la dispersión bancaria de sueldos y cuál la de CTS.'
	)
	cci = fields.Char(
		string='CCI',
		help='Código de Cuenta Interbancario (20 dígitos). Requerido para pagos '
			 'interbancarios en la dispersión de haberes.'
	)
