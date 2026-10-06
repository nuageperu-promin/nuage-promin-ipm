# -*- coding: utf-8 -*-

{
	'maintainer': 'Nuage Peru S.A.C.',
	'license': 'Other proprietary',
	'name': 'Búsqueda RUC/DNI',

	'summary': """
		Obtener datos con RUC o DNI
		""",

	'description': """
		Obtener los datos por RUC o DNI
	""",


	'category': 'Uncategorized',
	'version': '19.0.1.3',
	#'license': 'Other proprietary',
	'depends': ['base', 'l10n_pe'],

	'data': [
		'security/ir.model.access.csv',
		'data/res_city_data.xml',
		'wizard/busqueda_view.xml',
		'views/company_view.xml',
		'views/res_partner_view.xml',
	],
	'demo': [],
	'installable': True,
	'auto_install': False,
	'application': True,
	"sequence": 1,
}
