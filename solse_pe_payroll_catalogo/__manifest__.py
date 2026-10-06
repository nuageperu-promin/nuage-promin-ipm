# -*- coding: utf-8 -*-

{
	'maintainer': 'Nuage Peru S.A.C.',
	'name': 'Nómina Peruana - Integración con Catálogo SUNAT (Enterprise)',
	'summary': 'Puente de menús: reubica la Nómina PE bajo la raíz SOLSE '
			   'cuando la suite CPE (solse_pe_catalogo) está instalada.',
	'category': 'Human Resources/Payroll',
	'version': '19.0.0.2',
	'license': 'Other proprietary',
	'depends': [
		'solse_pe_payroll',
		'solse_pe_catalogo',
	],
	'data': [
		'views/menu_views.xml',
	],
	'installable': True,
	'auto_install': True,
}
