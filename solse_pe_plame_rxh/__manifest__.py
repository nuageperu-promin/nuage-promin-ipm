# -*- coding: utf-8 -*-
# Distributed under the MIT software license.

{
	'name': "Perú - PLAME Recibos por Honorarios",
	'summary': "Genera los archivos .ps4 y .4ta para importar al PDT PLAME",
	'description': """
		Genera los archivos de importación de Prestadores de Servicios de 4ta
		Categoría al PDT Planilla Electrónica - PLAME (F.V. 0601):

		* Estructura 7  -> archivo .ps4 (maestro de prestadores)
		* Estructura 20 -> archivo .4ta (detalle de comprobantes)

		Base normativa: Anexo 3 de la R.M. N.° 121-2011-TR, modificado por la
		R.S. N.° 028-2018/SUNAT. Tablas paramétricas: Anexo 2 (Tablas 3, 23 y 25).

		Los comprobantes se seleccionan por criterio de PERCEPCIÓN: entra al
		periodo todo recibo cuyo pago se produjo dentro del mes declarado,
		sin importar su fecha de emisión.
	""",
	'category': 'Financial',
	'version': '19.0.1.2.0',
	'license': 'Other proprietary',
	'depends': [
		'account',
		'l10n_latam_invoice_document',
		'solse_pe_rate_api',
		'solse_pe_accountant',
	],
	'data': [
		'security/ir.model.access.csv',
		'views/res_partner_views.xml',
		'views/account_tax_views.xml',
		'views/account_move_views.xml',
		'views/res_config_settings_views.xml',
		'wizard/plame_rxh_exportar_views.xml',
		'views/menu_views.xml',
	],
	'installable': True,
	'application': False,
}
