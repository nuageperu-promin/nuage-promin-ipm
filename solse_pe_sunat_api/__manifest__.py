# -*- coding: utf-8 -*-

{
	'maintainer': 'Nuage Peru S.A.C.',
	'name': 'SOLSE: API SUNAT',

	'summary': """
		SOLSE: API SUNAT""",

	'description': """
		SOLSE: API SUNAT
	""",

	'category': 'account',
	'version': '19.0.1.2',
	'license': 'Other proprietary',
	'depends': [
		'base',
		'account',
		'l10n_pe',
		'solse_pe_catalogo',
	],
	'data': [
		'security/sunat_api.xml',
		'security/ir.model.access.csv',
		'views/api_sunat.xml',
	],
	'qweb': [],
	'installable': True,
}
