# -*- coding: utf-8 -*-

{
	'maintainer': 'Nuage Peru S.A.C.',
	'name': 'SOLSE CPE Guias',

	'summary': """
		Emision de guias electronicos a SUNAT - Perú""",

	'description': """
		Facturación electrónica - Perú
		Emision de guias electronicos a SUNAT - Perú

		Versión 19.0.2.0.0 - Actualización 01/06/2026 (F1)
		--------------------------------------------------
		- Refactor de documentos relacionados a One2many
		  (soporta múltiples documentos por guía)
		- Carga del Catálogo 61 SUNAT completo (incluye nuevos
		  códigos 92-95 publicados el 01/06/2026)
		- Tag IssuerParty con RUC del emisor del documento relacionado
		  (cumple ERR-3380, ERR-3382, ERR-3614)
		- Validaciones cliente-side ERR-3445, ERR-3493, ERR-3612, ERR-3613

		Versión 19.0.3.0.0 - Actualización 01/06/2026 (F2)
		--------------------------------------------------
		- Nuevo campo "Fecha de entrega de bienes al transportista"
		  (pe_delivery_date) obligatorio para modalidad 01-Público
		- Tag UBL nuevo: cac:LoadingTransportEvent/cbc:OccurrenceDate
		  (reemplaza a OBS-4385, OBS-4386 y ERR-3407)
		- Validaciones ERR-3617, ERR-3618, ERR-3619
		- Refactor del orden de elementos en cac:ShipmentStage para
		  cumplir con la secuencia XSD UBL 2.1

		Versión 19.0.4.0.0 - Actualización 01/06/2026 (F3+F4+F5+F6)
		-----------------------------------------------------------
		- Indicadores SUNAT (cbc:SpecialInstructions):
		  * pe_traslado_total_dam (motivos 08/19 + docs 50/52)
		  * pe_traslado_contenedor_mc (motivos 08/09 + doc 91)
		  * pe_transbordo_programado (modalidad 01)
		  * pe_registro_vehiculos_conductores (modalidad 01)
		  * pe_vehiculos_m1_l
		- Nuevo modelo pe.stock.contenedor para contenedores y precintos
		  (cac:TransportHandlingUnit/cac:TransportEquipment con ID + TraceID)
		- Sub-régimen Motivo 19 + Doc 92 (Traslado mercancía extranjera):
		  suprime Information, GrossWeight, TotalHandling, contenedores y
		  reemplaza DespatchLines reales por una línea dummy obligatoria
		  por XSD (ERR-3623 a ERR-3630)
		- Validaciones nuevas: ERR-3615, ERR-3485, ERR-3621, ERR-3631, ERR-3632
		- Fix: eliminado código duplicado en bloque modalidad 02
		- Fix: eliminado mapeo incorrecto pe_fleet_ids?TransportEquipment
		Versión 19.0.4.0.2 - HOTFIX placa vehículo en TransportEquipment
		----------------------------------------------------------------
		- Corrige ERR-2566 SUNAT: la placa del vehículo principal ahora se
		  emite en cac:TransportHandlingUnit/cac:TransportEquipment/cbc:ID
		  (donde SUNAT realmente la valida), no solo en cac:ShipmentStage/
		  cac:TransportMeans/cac:RoadTransport/cbc:LicensePlateID que es
		  meramente informativo.
		- Soporte para vehículos secundarios via cac:AttachedTransportEquipment
		  (máx 2 según ERR-4389).
		- TransportHandlingUnit ahora agrupa correctamente Packages
		  (contenedores) + TransportEquipment (vehículo) en una sola
		  unidad, respetando orden UBL 2.1.
		- Lógica de emisión de placa:
		    Mod 02 sin M1/L ? emite (obligatorio)
		    Mod 01 + Registro vehículos ? emite (obligatorio)
		    Mod 01 sin Registro vehículos ? no emite (placa va en CarrierParty)
		    M1/L ? no emite
		- Vista: las grillas Documentos relacionados y Contenedores ahora
		  ocupan el ancho completo (col="1") para mejor legibilidad.
		Versión 19.0.4.0.3 - HOTFIX documento de identidad del conductor
		----------------------------------------------------------------
		- Corrige ERR-2571 SUNAT: el cbc:ID/@schemeID del DriverPerson
		  no puede ser '6' (RUC). El Catálogo 06 SUNAT acepta para
		  conductor solamente: 1 (DNI), 4 (Carnet extranjería),
		  7 (Pasaporte), A (Cédula diplomática).
		- Nuevo método helper _obtener_doc_identidad_conductor que:
		    * Si partner tiene RUC persona natural (inicia con '10' +
		      DNI + dígito verificador), extrae el DNI subyacente
		      automáticamente y emite schemeID='1'.
		    * Otros casos: devuelve lo que hay y deja diagnóstico SUNAT.
		- Nueva validación cliente _validar_documentos_conductores que
		  bloquea antes del envío si algún conductor tiene RUC empresarial
		  ('20...') o tipo de documento no válido para SUNAT.

		Versión 19.0.4.8 - Transporte público con vehículos y conductores
		------------------------------------------------------------------
		Reglas de validación SUNAT publicadas al 20/06/2026 (GRE-Remitente,
		campos 44 al 55). Habilita el caso "modalidad 01-Público en el que
		el remitente consigna los vehículos y conductores del transportista"
		(último párrafo del numeral 3.1 del artículo 3 de la RS 255-2015/
		SUNAT), con el que el transportista queda exceptuado de emitir su
		GRE - Transportista.

		- Nuevo campo fleet.vehicle.pe_tuce (TUCE / Certificado de
		  habilitación vehicular) con validación de formato ERR-3355
		  (10 a 15 caracteres, mayúsculas y números, no solo ceros).
		- Nuevo campo pe.stock.fleet.pe_tuce, que se arrastra desde el
		  vehículo en el onchange y es editable por guía.
		- Nuevo campo res.partner.pe_mtc_number (Registro MTC) emitido en
		  cac:CarrierParty/cac:PartyLegalEntity/cbc:CompanyID (OBS-4391).
		- FIX ERR-3357 / ERR-2568 / ERR-2572: cac:DriverPerson nunca se
		  emitía en modalidad 01. Ahora se emite cuando el indicador de
		  registro de vehículos y conductores está activo.
		- FIX ERR-3358: el cbc:JobTitle salía "Principal" en TODAS las
		  líneas. Ahora es "Principal" solo el vehículo marcado como tal y
		  "Secundario" el resto (máx. 2).
		- Nuevo tag cac:ApplicableTransportMeans/cbc:RegistrationNationalityID
		  con la TUCE del vehículo principal y de los secundarios; se
		  suprime en modalidad 01 sin el indicador (ERR-3452, ERR-3454).
		- Nuevo helper stock.picking._emite_vehiculos_conductores() como
		  única fuente de verdad para placa y conductores.
		- Nueva validación _validar_vehiculos_conductores(): ERR-2566,
		  ERR-2567, ERR-2572, ERR-2573, ERR-3354, ERR-3355, ERR-3358,
		  ERR-3362, ERR-3455, ERR-3616, OBS-4389, OBS-4399.
		- Vista: la grilla de vehículos ahora es visible en modalidad 01
		  cuando el indicador está activo, y se oculta en traslados M1/L.
		- Corregido el texto de ayuda del indicador, que describía el
		  comportamiento inverso al normado.

		Versión 19.0.4.9 - Representación impresa de la guía
		------------------------------------------------------------------
		- El bloque "UNIDAD DE TRANSPORTE / CONDUCTOR" del reporte QWeb
		  estaba condicionado a pe_transport_mode == '02', por lo que en
		  modalidad 01-Público con registro de vehículos y conductores el
		  PDF no mostraba placa, conductor ni licencia aunque sí viajaran
		  en el XML. Ahora usa el mismo helper
		  _emite_vehiculos_conductores() que el generador UBL.
		- En modalidad 01 con el indicador se imprimen ambas cajas:
		  TRANSPORTISTA (con Registro MTC) y UNIDAD DE TRANSPORTE.
		- Se agregan al impreso la TUCE / Certificado de habilitación, el
		  Registro MTC del transportista y la marca PRINCIPAL / SECUNDARIO
		  por vehículo.

		Versión 19.0.4.10 - OBS-4399 configurable y ERR-3451
		------------------------------------------------------------------
		- La TUCE deja de ser bloqueante por defecto. En el Excel oficial de
		  reglas al 20/06/2026 (campo 47) la 4399 es de tipo OBSERVACIÓN, no
		  ERROR: sin la TUCE la guía se acepta igual y el CDR vuelve
		  "aceptado con observaciones". Bloquear el envío era más estricto
		  que la norma.
		- Nuevo parámetro del sistema
		  'solse_pe_cpe_guias.tuce_obligatoria' (data/parametros_config.xml,
		  noupdate="1", valor por defecto 0). Se edita desde Ajustes >
		  Técnico > Parámetros del sistema, sin actualizar el módulo por
		  consola y sin reiniciar el servicio.
		- Nuevo helper stock.picking._obs_es_bloqueante(clave, defecto),
		  reutilizable para futuras reglas de tipo OBSERV. Tolera el
		  parámetro ausente, vacío o borrado por accidente.
		- Cuando se emite sin TUCE se deja advertencia en el log del
		  servidor con el número de guía.
		- FIX ERR-3451: no estaba validado. Activar a la vez 'Registro de
		  vehículos y conductores del transportista' y 'Traslado en
		  vehículos categoría M1 o L' emitía ambos SpecialInstructions
		  (rechazo SUNAT) y además _emite_vehiculos_conductores() suprimía
		  placa y conductor en silencio.

		Versión 19.0.4.19 - Fix bloqueante: contenedor sin bultos era inemitible
		------------------------------------------------------------------
		Contraste con las Reglas de Validación publicadas al 20/06/2026.
		- FIX bloqueante: validate_eguide() rellenaba 'Cantidad Bultos' con 1
		  cuando venía vacía, ANTES de _validar_indicadores_y_contenedores(),
		  así que toda guía con contenedor caía en el ERR-3621 con los bultos
		  visiblemente en cero. El relleno ahora solo aplica sin contenedores.
		  Los tests existentes no lo detectaban porque llamaban a la
		  validación de contenedores directamente y no a validate_eguide().
		- button_validate() ya no completa los bultos con las unidades
		  movidas cuando la guía tiene contenedores (nuevo helper
		  _completar_bultos_desde_movimientos); onchange que pone los bultos
		  en cero al registrar el primer contenedor; en la vista el campo
		  queda de solo lectura mientras haya contenedores.
		- FIX ERR-3631/ERR-3632: se bloqueaba "traslado total + contenedor".
		  Ninguna de las dos reglas prohíbe el contenedor: ambas exigen
		  bultos solo cuando NO hay contenedor (el ERR-3422 contempla esa
		  combinación expresamente). Unificado como contenedor XOR bultos
		  para 08/09/19 con doc 50/52; para el motivo 09 la regla es ERR-3419.
		  El test que consagraba la lectura errónea se invirtió.
		- Nueva validación ERR-3422: con contenedor y sin indicador de
		  manifiesto de carga, el precinto es obligatorio (motivo 09, o
		  08/09/19 con traslado total).
		- Nuevas validaciones ERR-3420 (máximo dos contenedores) y ERR-3421
		  (número de contenedor repetido).
		- Vista: el indicador de traslado total de la DAM/DS ahora es visible
		  también en el motivo 09 (ERR-3392 ya lo admitía en el modelo).
		- Eliminada comprobación duplicada de peso bruto. Mensaje del
		  ERR-3621 indica cuántos contenedores y bultos hay.

		Versión 19.0.4.20 - Punto de extensión obtener_servidor()
		------------------------------------------------------------------
		- Nuevo método solse.cpe.eguide.obtener_servidor(), usado por
		  prepare_sunat_auth() y get_sunat_ticket_status() en lugar de leer
		  empresa.pe_cpe_eguide_server_id directamente. Prerequisito de
		  solse_pe_cpe_guias_transp (Guía Transportista 31), que lo redefine
		  para apuntar a su propio servidor sin duplicar firma, envío ni CDR.
		  Comportamiento de la GRR sin cambios.
		- Deprecaciones: eliminados los `states=` (ignorados desde v17) y el
		  default `_company_default_get` (inexistente desde v13) de
		  solse.cpe.eguide; company_id ahora usa self.env.company y su solo
		  lectura por estado está en la vista. Eliminados los @api.model de
		  métodos que llamaban ensure_one().
		- Reporte: clases Bootstrap 4 (col-xs-*, text-right) reemplazadas
		  por sus equivalentes BS5 de Odoo 19.
		- XML: en motivo 08 con contenedor ya no se emite
		  cbc:TotalTransportHandlingUnitQuantity con valor 0 (chocaba con
		  ERR-3621; con contenedor el tag no debe existir).

		Versión 19.0.4.21 - Orden XSD en TransportHandlingUnit
		------------------------------------------------------------------
		- Rechazo 0306 del homologador en toda guía con contenedor Y placa:
		  en el XSD de cac:TransportHandlingUnit (UBL 2.1) cac:TransportEquipment
		  precede a cac:Package. Desde 19.0.4.0.2 se emitían al revés
		  (comentado como "orden UBL", pero invertido). Confirmado en beta con
		  los casos GRR-02 y GRR-04 del laboratorio.

		Versión 19.0.4.22 - Importación (08): puerto de partida obligatorio
		------------------------------------------------------------------
		- Rechazo 3365 del homologador: en el motivo 08 el punto de PARTIDA
		  es el puerto/aeropuerto de desembarque; sin él SUNAT exige el
		  establecimiento anexo de partida (no implementado). Ahora la
		  validación local exige el puerto en 08 igual que en 09.
		- 3364: la comparación de ubigeo contra el puerto se hace con el
		  punto de partida en 08 y con el de llegada en 09 (antes siempre
		  llegada).
	""",

	'category': 'Financial',
	'version': '19.0.4.22',
	'license': 'Other proprietary',
	'depends': [
		'stock',
		'fleet',
		'account',
		'account_fleet',
		'stock_delivery',
		'product_expiry',
		'solse_pe_cpe',
	],
	'data': [
		'data/secuencias_por_compania.xml',
		'security/ir.model.access.csv',
		'views/pe_sunat_eguide_view.xml',
		'views/company_view.xml',
		'views/stock_view.xml',
		'views/res_partner.xml',
		'views/fleet_vehicle_view.xml',
		'views/cpe_server_view.xml',
		'views/detalle_trasnferencia_view.xml',
		'data/sunat_eguide_data.xml',
		'data/parametros_config.xml',
		'data/pe_puerto_data.xml',
		'views/pe_puerto_view.xml',
		'report/report_guia.xml',
	],
	'post_init_hook': 'post_init_hook',
	'installable': True,
	'price': 210,
	'currency': 'USD',
}
