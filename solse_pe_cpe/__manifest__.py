# -*- coding: utf-8 -*-

{
	'maintainer': 'Nuage Peru S.A.C.',
	'license': 'Other proprietary',
	'name': 'CPE SUNAT',

	'summary': """
		Emision de comprobantes electronicos a SUNAT - Perú""",

	'description': """
		Facturación electrónica - Perú 
		Emision de comprobantes electronicos a SUNAT - Perú
	""",

	'category': 'Financial',
	'version': '19.0.1.30',
	#'license': 'Other proprietary',
	'depends': [
		'solse_pe_edi',
		'account_debit_note',
	],
	# M-10: se importan xmlsec (cpe_xml.py:7, cpe_core.py:8) y pysimplesoap
	# (solse_cpe.py:12, cpe_xml.py:12). Sin declararlo, la instalacion muere
	# con un ImportError crudo en vez del mensaje de Odoo que nombra el
	# paquete que falta.
	'external_dependencies': {
		'python': ['xmlsec', 'pysimplesoap'],
	},
	'data': [
		'security/solse_pe_cpe_security.xml',
		'security/ir.model.access.csv',
		'data/cpe_data.xml',
		'data/cpe_signature.xml',
		'data/tareas_programadas.xml',
		'data/secuencias_por_compania.xml',
		'data/template_email_cpe.xml',
		'views/account_move_view.xml',
		'views/cpe_certificate_view.xml',
		'views/cpe_server_view.xml',
		'views/company_view.xml',
		'views/solse_cpe_view.xml',
		'views/account_payment_term_view.xml',
		#'report/report_invoice.xml',
		#'report/report_invoice_ticket.xml',
		'wizard/account_invoice_debit_view.xml',
		'wizard/account_payment_register_views.xml',
		
	],
	'assets': {
		'web.report_assets_common': [
			'/solse_pe_cpe/static/src/css/reportes.css',
		],
		'web.assets_backend': [
			'/solse_pe_cpe/static/src/js/tax_totals_pe.js',
		],
	},
	'installable': True,
	'price': 600,
	'currency': 'USD',
}
