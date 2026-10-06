# -*- coding: utf-8 -*-

{
	'maintainer': 'Nuage Peru S.A.C.',
	'name': 'SIRE SUNAT - Ventas',
	'version': '19.0.0.13',
	'license': 'Other proprietary',
	'summary': 'Ventas para la declaración de SIRE a SUNAT',
	'category': 'Financial',
	'description': "Libros electronicos de ventas para SIRE.",
	'depends': [
		'l10n_latam_invoice_document',
		'solse_pe_edi',
		'solse_pe_cpe',
		'solse_pe_sunat_api',
	],
	'data': [
		'security/sunat_sire_security.xml',
		'security/ir.model.access.csv',
		'views/product_view.xml',
		'views/account_payment_views.xml',
		'views/account_move_view.xml',
		'views/account_move_rvie_view.xml',
		'views/res_bank_views.xml',
		'views/l10n_latam_document_type_view.xml',
		'views/sire_report_views.xml',
		'views/sire_menu_view.xml',
	],
	'external_dependencies': {
		'python': ['pandas', 'xlsxwriter', 'openpyxl'],
	},
	'auto_install': False,
	'installable': True,
	'application': True,
	'sequence': 1,
}
