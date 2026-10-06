# -*- coding: utf-8 -*-

# Módulo propietario. Todos los derechos reservados.

{
	'maintainer': 'Nuage Peru S.A.C.',
	'name': 'PLE 07 - Registro de Activos Fijos Sunat Perú TXT XLS (Enterprise)',
	'version': '19.0.1.4.1',
	'license': 'Other proprietary',
	'summary': """
		Genera las estructuras 7.1, 7.3 y 7.4 del PLE de Sunat Perú
		(Registro de Activos Fijos) a partir de account.asset, y el
		formato físico 7.1 en PDF.
	""",
	'category': 'Financial',
	'description': """
		Registro de Activos Fijos - PLE SUNAT (Libro 7).

		Estructuras generadas (libro anual):
		  7.1 - Detalle de los activos fijos revaluados y no revaluados
		  7.3 - Detalle de la diferencia de cambio
		  7.4 - Detalle de los activos bajo arrendamiento financiero

		Existe en dos variantes excluyentes que solo difieren en de qué
		módulo toma account.asset (ver el comentario junto a 'depends');
		la Enterprise se regenera desde la Community con
		sincronizar_ple07.py.

		v19.0.1.4.0 (físicos, tanda b — libro 7 completo):
		  - Formato físico 7.2 (activos revaluados) desde el TXT 7.1.
		  - account.asset.fecha_revaluacion: las revaluaciones (acumuladas al
		    31.12) solo rigen en los ejercicios que cierran desde esa fecha.

		v19.0.1.3.1 (L9.4):
		  - Los tres PDF envuelven cada documento en div.article: sin él
		    wkhtmltopdf los leía sin charset (tildes en mojibake).
		  - 7.1: descripción completa del activo (el C11 del TXT va a 40).

		v19.0.1.3.0 (físicos, tanda a):
		  - Formatos físicos 7.3 y 7.4 en PDF (plantilla oficial). La
		    depreciación acumulada histórica del 7.3 toma el C29 del 7.1
		    del mismo activo y aplica el mismo parámetro B-9.

		v19.0.1.2.1 (L9.1, B-10):
		  - La depreciación del ejercicio ignora los asientos de venta o
		    baja enlazados al activo (asset_move_type, Enterprise).

		v19.0.1.2.0 (L9, B-9):
		  - Físico 7.1: presentación de las bajas configurable
		    (solse_pe_ple_07.dep_historica_bajas = descontar | acumular,
		    por defecto descontar: el bien retirado queda en 0 / 0).

		v19.0.1.1.1 (L8.1, AF7-02):
		  - moneda_adquisicion_id / valor_adquisicion_me pasan a compute
		    EDITABLE: sin apuntes de origen conservan lo informado (antes
		    el ORM los vaciaba y el activo nunca entraba al 7.3).

		v19.0.1.1.0 (L8.1):
		  - Formato físico 7.1 en PDF (R.S. 234-2006, plantilla oficial):
		    26 columnas con las derivadas (valor histórico y ajustado al
		    31.12, depreciación acumulada histórica y ajustada) y totales.
		  - TXT en ANSI (cp1252) con la transliteración de ple_pro.

		v19.0.0.1:
		  - Estructuras 7.1 / 7.3 / 7.4 en TXT (Latin-1) y Excel.
		  - Campos SUNAT en account.asset (Tablas 13, 18, 19, 20; marca,
		    modelo, serie/placa, datos de leasing).
		  - CUO y correlativo consistentes con el Libro Diario (ple_pro).
		  - Mejoras: activos hijos (parent_id) del ejercicio se reportan
		    como mejora (C17) del activo padre.
	""",
	# ? Este modulo es la variante ENTERPRISE. Usa el account_asset nativo.
	# En Odoo 19 COMMUNITY hay que instalar solse_pe_ple_07, que usa
	# solse_pe_activo_fijo.
	'depends': [
		'account_asset',
		'solse_pe_ple_pro',
	],
	'data': [
		'security/ir.model.access.csv',
		'security/sunat_ple_security.xml',
		'data/parametros.xml',
		'reports/formato_7_1.xml',
		'reports/formato_7_3_7_4.xml',
		'reports/formato_7_2.xml',
		'views/account_asset_views.xml',
		'views/ple_report_views.xml',
	],
	'external_dependencies': {
		'python': [
			'pandas',
			'xlsxwriter',
		],
	},
	'auto_install': False,
	'installable': True,
	'application': True,
	'sequence': 1,
}
