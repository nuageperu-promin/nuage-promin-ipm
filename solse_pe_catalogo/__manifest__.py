# -*- coding: utf-8 -*-

{
	'maintainer': 'Nuage Peru S.A.C.',
	'name': 'Catalogo SUNAT',

	'summary': """
		Catalogo SUNAT""",

	'description': """
		Catalogo SUNAT
	""",

	'category': 'account',
	'version': '19.0.1.5',
	'license': 'Other proprietary',
	'depends': [
		'base',
		'l10n_pe',
	],
	'data': [
		'security/pe_datas_security.xml',
		'security/ir.model.access.csv',
		'data/pe_datas.xml',
		'data/pe_datas_n2.xml',
		'data/pe_datas_adicionales.xml',
		'data/pe_datas_tabla28_tabla34.xml',
		'views/pe_datas_view.xml',
	],
	'qweb': [],
	'post_init_hook': 'post_init_hook',
	'installable': True,
}
