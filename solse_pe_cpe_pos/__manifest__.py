# -*- coding: utf-8 -*-

{
	'maintainer': 'Nuage Peru S.A.C.',
	'name': 'CPE desde POS',
	'summary': """
		Facturación electronica desde POS""",
	'description': """
		Facturación electronica desde POS
	""",
	'category': 'Operations',
	'version': '19.0.1.12',
	'license': 'Other proprietary',
	'depends': [
		'base_setup',
		'solse_pe_edi',
		'solse_pe_cpe',
		'point_of_sale',
		'sale_management',
		'pos_sale',
		'pos_loyalty',
	],
	'data': [
		'security/solse_pos_security.xml',
		'security/ir.model.access.csv',
		'views/pos_config_view.xml',
		'views/pos_session_view.xml',
	],
	'assets': {
		'point_of_sale._assets_pos': [

			# Todos los archivos JS y XML (como hace point_of_sale nativo)
			'solse_pe_cpe_pos/static/src/**/*',
		],
	},
	'post_init_hook': 'post_init_hook',
	'installable': True,
	'price': 150,
	'currency': 'USD',
}
