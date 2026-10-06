# -*- coding: utf-8 -*-

{
	'maintainer': 'Nuage Peru S.A.C.',
	'license': 'Other proprietary',
	'name': 'Extension CPE para Enterprise',

	'summary': """
		Extension CPE para Enterprise""",

	'description': """
		Extension CPE para Enterprise
	""",

	'category': 'Financial',
	'version': '19.0.0.4',

	'depends': [
		'account',
		'solse_pe_cpe',
	],
	
	'data': [
		'report/report_invoice_p2.xml',
		'report/report_invoice_p3.xml',
		'report/report_invoice_p4.xml',
		'report/report_invoice_p5.xml',
		'report/report_invoice_p6.xml',
		'report/report_ticket_n1.xml',
		'views/journal_view.xml',
	],
	'assets': {
		'web.report_assets_common': [
			'/solse_pe_cpe_pdf_ee/static/src/css/reportes.css',
		],
	},
	'installable': True,
	'price': 15,
	'currency': 'USD',
}
