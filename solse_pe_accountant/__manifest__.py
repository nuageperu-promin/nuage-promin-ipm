# -*- coding: utf-8 -*-

{
	'maintainer': 'Nuage Peru S.A.C.',
	'name': 'Perú - Contabilidad',
	'summary': "Contabilidad básica para Perú",
	'description': """
		* Gestiona asientos de apertura
		* Tipo de cambio según normas SUNAT (fecha correcta por tipo de movimiento)
		* Cuentas contables configurables para detracciones y retenciones
		* Registro del pago de detracciones y retenciones
		* Registro de glosa para los asientos contables
	""",
	'category': 'Financial',
	'version': '19.0.1.4',
	'license': 'Other proprietary',
	'depends': [
		'account',
		'solse_pe_rate_api',
		'solse_pe_edi',
		'solse_pe_cpe',
	],
	'data': [
		'security/ir.model.access.csv',
		'views/account_account_views.xml',
		'views/res_config_settings_view.xml',
		'views/res_partner_view.xml',
		'wizard/asignar_tabla34_views.xml',
		'wizard/diagnostico_tabla34_views.xml',
		'views/account_move_view.xml',
		'wizard/account_payment_register_views.xml',
	],
	'installable': True,
	'price': 690,
	'currency': 'USD',
}
