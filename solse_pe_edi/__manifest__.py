# -*- coding: utf-8 -*-

{
	'maintainer': 'Nuage Peru S.A.C.',
	'name': 'F&M SOLSE EDI',

	'summary': """
		F&M SOLSE EDI""",

	'description': """
		F&M SOLSE EDI
	""",

	'category': 'account',
	'version': '19.0.1.4',
	'license': 'Other proprietary',
	'depends': [
		'base',
		'account',
		'l10n_pe',
		'l10n_latam_invoice_document',
		'solse_pe_catalogo',
	],
	'data': [
		'security/pe_datas_security.xml',
		'security/ir.model.access.csv',
		'wizard/migracion_numero_compra_views.xml',
		'data/account_tax_data.xml',
		'data/l10n_latam_document_type_data.xml',
		'data/res_currency_data.xml',
		'views/l10n_latam_document_type_view.xml',
		'views/company_view.xml',
		'views/accoun_move_view.xml',
		'views/product_view.xml',
		'views/res_country_data.xml',
		'views/res_partner_view.xml',
		'views/res_currency.xml',
	],
	'qweb': [],
	'installable': True,
}
