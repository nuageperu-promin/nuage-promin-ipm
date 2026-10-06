# -*- coding: utf-8 -*-

{
	'maintainer': 'Nuage Peru S.A.C.',
	'name': 'Tipo de cambio para Perú',
	'version': '19.0.1.3',
	'license': 'Other proprietary',
	'category': 'Extra Tools',
	'summary': 'Automatización de tipo de cambio para Perú',
	'depends': [
		'base',
		'account',
		'solse_pe_vat',
	],
	'data': [
		'security/ir.model.access.csv',
		'data/ir_cron_data.xml',
		'views/account_move_view.xml',
		'views/res_currency_views.xml',
		'wizard/rango_fecha_view.xml',
	],
	'installable': True,
	'sequence': 1,
}
