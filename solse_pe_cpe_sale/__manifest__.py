# -*- coding: utf-8 -*-

{
	'maintainer': 'Nuage Peru S.A.C.',
	'name': 'CPE Ventas',

	'summary': """
		Enlace del modulo de ventas con la creacion de facturas electronicas""",

	'description': """
		Facturación electrónica - Perú 
		Enlace del modulo de ventas con la creacion de facturas electronicas
	""",

	'category': 'Financial',
	'version': '19.0.0.3',
	'license': 'Other proprietary',
	'depends': [
		'sale',
		'sale_management',
		'solse_pe_edi',
		'solse_pe_cpe',
	],
	'data': [
		'data/tarea_programada.xml',
		'views/sale_order_view.xml',
		'views/detalle_ventas_view.xml',
		'views/detalle_factura_cliente_view.xml',
		#'report/report_sale_ticket.xml',
	],
	'assets': {
		'web.assets_backend': [
			'/solse_pe_cpe_sale/static/src/estilos.scss',
		],
	},
	'installable': True,
	'price': 60,
	'currency': 'USD',
}
