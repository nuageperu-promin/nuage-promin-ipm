# -*- coding: utf-8 -*-

{
	'maintainer': 'Nuage Peru S.A.C.',
	'name': 'SIRE SUNAT - Compras',
	'version': '19.0.2.6',
	'license': 'Other proprietary',
	'summary': 'Compras para la declaración de SIRE a SUNAT',
	'category': 'Financial',
	'description': """
		Contempla los libros electronicos de Compras para SIRE.
		v0.2: TUS para reemplazo, ajustes posteriores 5.18/5.19/5.24/5.25,
		      creacion de facturas con desglose de montos, compatibilidad
		      sin solse_pe_cpe, fixes de URLs SUNAT.
		v1.1: Precision milimetrica en montos (price_include), proveedor base
		      para comprobantes sin RUC/DNI, tipo documento latam por codigo,
		      vista formulario de detalle en compras_recibidas,
		      creacion de contacto por nombre cuando tipo_doc_identidad es 0.
		      (ahora vive exclusivamente en solse_pe_purchase). Se agrega
		      dependencia explicita a solse_pe_purchase.
		v1.3: Refactor de obtener_montos_libro_compras:
		      - Filtra por tipo_afectacion_compra.aplica_rce (excluye lineas
		        internas y no domiciliadas).
		      - Soporta nro_col_importe_afectacion como fallback cuando la
		        linea no tiene impuestos vinculados (caso exonerada/inafecta).
		      - Eliminado dead code comentado y sobrescritura de cols 22/23/24
		        que pisaba con cero los valores distribuidos por afectacion.
		      - Manejo unificado de notas de credito y comprobantes anulados.
		v1.4: Fixes criticos de envio a SUNAT (reemplazo de propuesta RCE):
		      - Periodo en columna 3 del TXT pasa de YYYYMM00 a YYYYMM (SUNAT
		        rechazaba el archivo con 8 digitos en el periodo).
		      - Correlativo en columna 10 y en notas C/D (col 32) se envia sin
		        ceros adelante (ej. '63' en lugar de '00000063').
		      - reemplazar_propuesta fuerza tipo_informacion='reemplazar' y
		        regenera el TXT/ZIP para que el nombre lleve report_03='02'
		        en posiciones 28-29 (sin esto SUNAT rechaza con "Error en
		        Posicion 28, Codigo RCE Remplazar Propuesta 02"). Incluye
		        validacion visible al usuario indicando el cambio automatico.
		      - Eliminada llamada al endpoint inexistente _URL_REEMPLAZAR_ENV
		        (NameError silencioso). El numTicket se extrae de la respuesta
		        TUS o se consulta del listado de tickets recientes.
		      - confirmar_propuesta tambien fuerza tipo_informacion='aceptar'
		        por coherencia con la accion.
		      - enlazar_con_factura normaliza correlativos con lstrip('0')
		        para enlazar correctamente cuando el usuario ingreso el ref
		        del proveedor con padding (F001-00000063 vs F001-63).
		v1.4.1: Fix de Periodo en TXT para facturas con fecha_emision distinta
		        a fecha contable:
		      - Antes el campo 3 (Periodo) usaba invoice_date.strftime('%Y%m'),
		        lo cual era incorrecto cuando una factura se emitio en un mes
		        pero se anoto contablemente en otro (ej. factura 20-mar-2026
		        anotada con fecha contable 01-abr-2026 debia declararse con
		        periodo 202604, no 202603).
		      - Ahora usa fecha_inicio del reporte (basado en self.year/month
		        del SIRE, que ya esta derivado de la fecha contable porque
		        update_report filtra bills por date en lugar de invoice_date).
		v1.4.2: Fix de nombre del archivo para descarga manual (subida al portal
		        SUNAT sin usar el boton "Reemplazar propuesta" del sistema):
		      - En el mapa de get_default_filename, 'aceptar' y 'reemplazar'
		        ahora comparten report_03='02'. Antes 'aceptar' generaba nombre
		        con '01', pero como aceptar NO envia el TXT/ZIP (solo hace POST
		        al endpoint aceptapropuesta), el archivo no tenia uso real y
		        solo generaba confusion cuando el cliente lo descargaba para
		        subirlo manualmente al portal de reemplazo.
		      - reemplazar_propuesta y confirmar_propuesta YA NO fuerzan
		        cambio de tipo_informacion. El campo refleja la intencion del
		        usuario y debe ser visible como estado sin ser modificado
		        automaticamente.
		      - reemplazar_propuesta ahora aborta con mensaje claro si el
		        tipo_informacion es 'posterior' o 'poseriorperiodo' (que
		        generan nombres con '03'/'04' incompatibles con reemplazo).
		v1.4.3: Fix de Tipo de cambio (campo 27) para comprobantes en soles:
		      - SUNAT valida (inconsistencia 404 "Campo debe estar vacio")
		        que el campo 27 vaya VACIO cuando la moneda es PEN. Antes se
		        enviaba siempre '1.000', lo que generaba el rechazo en el
		        reporte de inconsistencias parametricas.
		      - Ahora: PEN -> campo vacio; moneda extranjera -> tipo de
		        cambio con 3 decimales.
	""",
	'depends': [
		'l10n_latam_invoice_document',
		'solse_pe_edi',
		'solse_pe_cpe',
		'solse_pe_purchase',
		'solse_pe_sire_ventas',
		'solse_pe_sunat_api',
		# `_split_serie_numero` y `get_sunat_number` viven en PLE Pro.
		# Se usaban sin declarar la dependencia: funcionaba solo si PLE
		# estaba instalado por casualidad. En una base sin el, confirmar
		# una factura de COMPRA fallaba con
		#
		#   AttributeError: 'account.move' object has no attribute
		#   '_split_serie_numero'
		#
		# El fallo salta al RECALCULAR `serie_compra`, no al instalar, asi
		# que no se detecta hasta que alguien registra una compra.
		'solse_pe_ple_pro',
	],
	'data': [
		'security/sunat_sire_security.xml',
		'security/ir.model.access.csv',
		'views/sire_report_views.xml',
		'views/compras_recibidas_form.xml',
		'views/sire_menu_view.xml',
		'views/account_move_sire_view.xml',
	],
	'external_dependencies': {
		'python': ['xlsxwriter', 'openpyxl'],
	},
	'auto_install': False,
	'installable': True,
	'application': True,
	'sequence': 1,
}
