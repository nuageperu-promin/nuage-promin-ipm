# -*- coding: utf-8 -*-

{
	'maintainer': 'Nuage Peru S.A.C.',
	'name': 'Nómina Peruana - Núcleo (Enterprise)',
	'summary': 'Localización peruana de nómina para Odoo 19 Enterprise: '
			   'maestros SUNAT/MTPE, versiones de empleado PE, parámetros '
			   'normativos versionados y mapeo contable PCGE.',
	'description': """
Núcleo de la localización peruana de nómina (SOLSE).

Incluye:
- Maestros normativos: régimen pensionario (T11), régimen laboral (T33),
  tipo de trabajador (T8), contratos MINTRA (T12), motivos de baja (T17),
  ocupaciones (T30), situación educativa (T9), situaciones especiales (T35),
  conceptos PLAME (T22 completa, 293 conceptos - versión 4.6).
- Extensión de hr.version (arquitectura de contratos de Odoo 19) con los
  campos exigidos por T-Registro y PLAME.
- Extensión de hr.employee: CUSPP, sistema pensionario, derechohabientes,
  cuentas de sueldo/CTS con CCI, descuentos judiciales, EPS, Vida Ley.
- Parámetros de nómina versionados por fecha (hr.rule.parameter): UIT, RMV,
  asignación familiar, tasas ONP/AFP/ESSALUD/SENATI, RMA trimestral con
  advertencia en dashboard, tramos de renta de 5ta, factores por régimen
  (general / pequeña empresa / microempresa / agrario).
- Mapeo contable por prefijo PCGE: asignación de cuentas por compañía,
  tolerante a planes contables con distinta longitud de código.
- Estructuras salariales del ciclo peruano (las reglas se instalan en el
  módulo de reglas - Fase 2).
	""",
	'category': 'Human Resources/Payroll',
	'version': '19.0.0.45',
	'license': 'Other proprietary',
	'pre_init_hook': '_pre_init_payroll_ee',
	'depends': [
		'hr',
		'hr_payroll',
		'hr_payroll_account',
		'hr_work_entry_enterprise',
		'hr_holidays',
		'l10n_pe',
		'l10n_latam_base',
	],
	'data': [
		'security/ir.model.access.csv',

		# Maestros (catálogos normativos)
		'data/data.xml',
		'data/academic_degree_data.xml',
		'data/employee_regime_data.xml',
		'data/type_contract_data.xml',
		'data/low_reason_data.xml',
		'data/data_relative_relation.xml',
		'data/pension_system_data.xml',
		'data/hr_employee_category_data.xml',
		'data/work.occupation.csv',
		'data/plame.lines.csv',

		# Parámetros de nómina PE + advertencia RMA
		'data/hr_rule_parameter_data.xml',

		# Estructuras salariales y reglas (Fase 2)
		'data/hr_salary_rule_category_data.xml',
		'data/hr_payroll_structure_data.xml',
		'data/hr_payroll_structure_adicionales_data.xml',
		'data/hr_salary_rule_bloque1_data.xml',
		'data/hr_salary_rule_bloque2_data.xml',
		'data/hr_salary_rule_bloque3_data.xml',
		'data/hr_salary_rule_bloque4_data.xml',
		'data/hr_salary_rule_bloque5_data.xml',
		'data/hr_salary_rule_bloque6_data.xml',
		'data/hr_salary_rule_bloque7_data.xml',
		'data/hr_salary_rule_bloque8_data.xml',
		'data/hr_salary_rule_bloque9_data.xml',
		'data/hr_salary_rule_bloque10_data.xml',

		# Vistas
		'views/maestros_views.xml',
		'views/rule_parameter_views.xml',
		'views/hr_version_views.xml',
		'views/hr_employee_views.xml',
		'views/mapeo_contable_views.xml',
		'views/res_company_views.xml',
		'wizard/asignar_cuentas_views.xml',
		'views/menu_views.xml',

		# Reportes (Fase 3)
		'report/boleta_pago_report.xml',
		'report/planilla_report.xml',
		'wizard/planilla_views.xml',
		'wizard/plame_views.xml',
		'wizard/bancos_views.xml',
		'wizard/afpnet_views.xml',
		'wizard/utilidades_views.xml',
		'data/hr_salary_rule_plame_extra_data.xml',

		# Inicialización (corre en cada instalación Y actualización)
		'data/inicializar_function.xml',
	],
	'installable': True,
	'application': True,
	'auto_install': False,
	'post_init_hook': 'post_init_hook',
	'sequence': 1,
}
