# -*- coding: utf-8 -*-

{
	'maintainer': 'Nuage Peru S.A.C.',
	'name': 'PLE SUNAT - PRO',
	'version': '19.0.1.6',
	'license': 'Other proprietary',
	'summary': 'Declaración de PLE a SUNAT',
	'category': 'Financial',
	'description': """
		Contempla los libros electrónicos de compras, ventas y libro diario.
		v19.0.0.2: Corrección de bugs críticos en Libro Diario (5.1) y Libro Mayor (6.1):
		  - CUO ahora usa ID del asiento contable (no número de comprobante)
		  - Correlativo consistente entre Libro Diario y Mayor para el mismo asiento
		  - Código de cuenta contable sin truncamiento (.rstrip eliminado)
		  - Tipo de comprobante vacío para asientos puros (no '00' inválido)
		  - Facturas de proveedor usan campo 'ref' para serie/número del proveedor
		  - Fecha de emisión correcta (invoice_date) para facturas en Libro Mayor
		  - Glosa del asiento correcta en Libro Mayor
		  - Filtro display_type correcto para Odoo 19
		v19.0.1.4: TXT 5.1/5.2/6.1 consolidan las líneas por llave SUNAT
		  (período, CUO, correlativo, cuenta, partner, tipo y número de
		  documento) dentro de cada asiento: una factura con varias líneas
		  a la misma cuenta repetía la llave única de la estructura y el
		  validador del PLE rechaza registros duplicados. Los totales del
		  archivo no cambian.
		v19.0.1.3: Tres correcciones normativas del TXT 5.1/6.1 detectadas
		  por auditoría contra la Estructura del PLE y el Anexo 3:
		  - C10 obligatorio: asientos sin comprobante llevan '00 — Otros'
		    (Tabla 10); el vacío del fix anterior incumplía la estructura.
		  - C14 opcional: vacío en asientos y pagos; solo comprobantes
		    llevan vencimiento (antes salía la fecha de creación del move).
		  - TXT en cp1252 con transliteración de tipográficos (— ' " …):
		    el encode latin-1 anterior volvía «?» las glosas con guion largo.
		v19.0.1.2: generate_report de 5.1 y 6.1 anclado a la compañía del
		  libro (with_company). `account.account.code` es company-dependent
		  en Odoo 19: generar desde otra compañía leía código False y el
		  TXT fallaba con «expected str instance, bool found».
		v19.0.1.1: Libro Diario (5.1) incluye SIEMPRE las cuentas de efectivo
		  y bancos (elemento 10). Antes, con «Eximido de presentar Caja y
		  Bancos» desmarcado, se excluían y los asientos salían descuadrados
		  (debe ? haber) en TXT y PDF. La exención del art. 13 de la R.S.
		  234-2006 opera al revés: llevar el detalle en el Diario exime del
		  1.1, nunca lo contrario. El check conserva su función correcta:
		  activar los campos extendidos C22-C30 en las líneas bancarias.
		v19.0.0.3: Validaciones adicionales y refinamientos SUNAT:
		  - Dato Estructurado (C20) retorna vacío por diseño. SUNAT lo marca como
		    opcional; el formato con '&' aplica solo a contribuyentes NO obligados
		    al SIRE (residual), y el CAR de 27 dígitos requiere integración con
		    los módulos SIRE que propaguen el código asignado por SUNAT al
		    account.move. Roadmap documentado en ple_report._dato_estructurado.
		  - Prefijo 'C' en correlativo para asientos de cierre (es_x_cierre)
		  - Validación previa: UserError si facturas de proveedor sin 'ref' y no
		    está activo el modo tolerante
		  - Campos centralizados solse_pe_serie/solse_pe_numero con lógica unificada
		  - Hook post-install para inicializar is_cash_account/is_bank_account
		  - Fallback más claro en C26 (descripción operación bancaria)
	""",
	'depends': [
		'l10n_latam_invoice_document',
		'solse_pe_edi',
		'solse_pe_cpe',
		'solse_pe_accountant',
	],
	'data': [
		'security/sunat_ple_security.xml',
		'security/ir.model.access.csv',
		'views/product_view.xml',
		'views/res_partner_views.xml',
		'views/account_payment_views.xml',
		'views/account_move_view.xml',
		'views/res_bank_views.xml',
		'views/l10n_latam_document_type_view.xml',
		'views/res_config_settings_view.xml',
		'views/ple_report_views.xml',
		'views/diagnostico_numeracion_views.xml',
		'views/ple_menu_view.xml',
	],
	'external_dependencies': {
		'python': [
			'pandas',
			'xlsxwriter',
			'openpyxl',
		],
	},
	'post_init_hook': 'post_init_hook',
	'auto_install': False,
	'installable': True,
	'application': True,
	'sequence': 1,
}
