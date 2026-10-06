# -*- coding: utf-8 -*-

{
	'maintainer': 'Nuage Peru S.A.C.',
	'name': 'Perú: Compras',

	'summary': "Perú: Compras (afectaciones, mapeo a columnas SIRE)",

	'description': """
		Perú: Compras
		Modulo donde se agrega complementos para adaptar compras a la localización peruana.

		v19.0.0.4:
		- Consolidación: este módulo es ahora el dueño exclusivo del modelo
		- Override de vista migrado de get_view (legacy) a _get_view (API v17+).
		- Refactor de onchange con helper _asignar_afectacion_por_impuesto.
		- impuesto_defecto_ids (Many2many) reemplaza al antiguo impuesto_defecto
		  (Many2one). Permite asignar múltiples impuestos por defecto al
		  seleccionar una afectación (caso retenciones: IGV + retención).

		v19.0.0.5:
		  aplica_rce, aplica_rce_no_dom.
		- Carga de 8 afectaciones por defecto (data XML noupdate=1).
		- post_init_hook que detecta los account.tax peruanos por
		  l10n_pe_edi_tax_code y los vincula a las afectaciones.

		v19.0.0.6:
		- Heurísticas de detección mejoradas: además de l10n_pe_edi_tax_code,
		  ahora detecta impuestos por nombre y por tax_group_id (cubre clientes
		  con plan contable estándar sin códigos SUNAT formales).
		- Nuevo wizard "Asistente: Configurar afectaciones" desde el menú,
		  para reconfigurar manualmente cuando el hook automático no detectó
		  todos los impuestos. UI con detección, selección y opción de
		  reemplazar configuración existente.
		- Fix v19: vista search del modelo afectación tenía un <group> con
		  expand y string que en v19 no es válido (debe ir simplemente como
		  <group>).

		v19.0.0.7:
		- Clasificación automática del IGV en sus tres destinos (DG, DGNG, DNG)
		  por patrones en el nombre del account.tax. Ej: "IGV 18%" ? DG;
		  "IGV 18% G NG" ? DGNG; "IGV 18% NG" ? DNG. Si solo hay un IGV
		  genérico, se usa el mismo para los tres (comportamiento válido).
		- Wizard ampliado con 3 campos Many2one separados para IGV-DG,
		  IGV-DGNG e IGV-DNG, prepoblados con la clasificación automática.
	""",

	'category': 'Financial',
	'version': '19.0.0.11',
	'license': 'Other proprietary',
	'depends': [
		'account',
		'solse_pe_catalogo',
		'solse_pe_cpe',
	],
	'data': [
		'security/ir.model.access.csv',
		'views/account_move_view.xml',
		'views/afectacion_compra.xml',
		'wizard/configurar_afectacion_wizard_view.xml',
		'data/afectacion_compra_data.xml',
	],
	'post_init_hook': '_post_init_hook',
	'installable': True,
	'price': 60,
	'currency': 'USD',
}
