# -*- coding: utf-8 -*-

{
	'name': "SOLSE CPE Guias Transportista",

	'summary': """
		Emision de guias electronicas de Transportista (31) a SUNAT - Perú""",

	'description': """
		Facturación electrónica - Perú
		Emision de Guías de Remisión Electrónica Transportista (tipo 31)

		Versión 19.0.1.0.0 - Port a Odoo 19 sobre solse_pe_cpe_guias 19.0.4.20
		-----------------------------------------------------------------------
		La GRR (09) y la GRT (31) conviven. La modalidad se define por Tipo de
		Operación (stock.picking.type) con fallback a la compañía y es
		editable por transferencia. Ningún override rompe la guía de remisión:
		todos llaman a super().

		Arquitectura: herencia de prototipo (solse.cpe.eguide.transport
		hereda de solse.cpe.eguide) y EGuideTransport(EGuide) para el XML.
		Solo se redefine lo que difiere entre la 09 y la 31.

		Estructura UBL 2.1 (hoja "Guía-Transportista2_0"):
		- cac:DespatchSupplierParty = transportista emisor (8, 9);
		  remitente en Shipment/Delivery/Despatch/cac:DespatchParty (16, 17).
		- Placa obligatoria en cac:TransportHandlingUnit/cac:TransportEquipment/
		  cbc:ID (35); secundarios en cac:AttachedTransportEquipment (máx 2).
		- TUCE en cac:ApplicableTransportMeans/cbc:RegistrationNationalityID
		  reutilizando el campo pe_tuce y el helper _agregar_tuce del base.
		- cac:Shipment/cbc:ID = "SUNAT_Envio" (49); GrossWeightMeasure con
		  unitCode KGM/TNE (52).
		- cbc:JobTitle Principal/Secundario (41, 45), máx 2 secundarios.
		- cac:Consignment/cac:LogisticsOperatorParty para el subcontratador
		  (60, 61); cac:OriginatorCustomerParty para el pagador tercero (62, 63).
		- cac:ShipmentStage/cac:CarrierParty con Registro MTC (10) y
		  autorización especial vía cac:AgentParty con schemeID de la entidad
		  autorizadora (11), ahora como Selection (SUCAMEC, DIGEMID, ...).
		- Indicadores cbc:SpecialInstructions (53 a 58); pagador de flete
		  obligatorio.
		- Líneas de bienes: detalle real (ID 1..n, cantidad, unidad del
		  catálogo 03, descripción) salvo que un documento relacionado los
		  ampare —GRE electrónica, 82, o 01/03/04/12/48 con traslado total—,
		  en cuyo caso va la línea única ID 0 con la anotación (reglas 3435,
		  3458, 4429).
		- 19.0.1.0.2: la línea 0 se admite con GRE FÍSICA (09 con serie
		  numérica), 82, o 01/04 físicos y 03/12/48 con traslado total; con
		  GRE electrónica el homologador la rechaza (3458) y el detalle solo
		  se observa (4434). Constraint ERR-3441 propio para documentos de
		  pickings en modalidad transportista (09 con serie numérica).
		- 19.0.1.0.3: los campos propios de la GRT eran obligatorios con solo
		  marcar "Es guía electrónica", también en modalidad remitente; al
		  estar ocultos el formulario avisaba "Faltan campos obligatorios"
		  sin señalar cuáles y la GRR no se podía guardar. Ahora solo son
		  obligatorios en modalidad transportista.
		- 19.0.1.0.4: el caso inverso — en modalidad transportista los
		  obligatorios de la GRR (motivo, modalidad de transporte,
		  transportista, fecha de entrega) quedaban ocultos pero activos.
		  Se anulan con pe_guide_mode = 'carrier'. La modalidad de guía es
		  ahora visible y editable en la transferencia (hasta numerar); el
		  valor por defecto sigue viniendo del tipo de operación.
		- Sin cac:SellerSupplierParty.
		- Documentos relacionados con cac:IssuerParty (pe.stock.documento.
		  relacionado del base) y catálogo 61 ampliado (31, 65-69).
		- Conductor con RUC persona natural emitido como DNI (ERR-2571,
		  helper del base).

		Validaciones cliente-side propias de la 31: partes, direcciones,
		vehículos y conductores (delegando en el base con modalidad 02),
		indicadores, y ERR-3441 con los patrones de la hoja
		Guía-Transportista2_0 (31, 50 con régimen 10/40, 65-69, 82).
		ERR-3620 / ERR-3622 son validaciones REST de SUNAT y no se comprueban
		localmente.

		Multiempresa: secuencias V001-/VG01- por compañía, correlativos con
		with_company, y el servidor de la GRT debe ser de la propia compañía.
		Si la compañía no define servidor de GRT se usa el de guías de
		remisión (mismo endpoint GRE de SUNAT).

		QR de la representación impresa con tipo 31 y URL de la GRT.

		Pendientes conocidos: cac:TransportEvent (59) se emite solo si el
		usuario llena el tipo de evento y no se probó contra el homologador;
		autorizaciones especiales por vehículo (37, 40) no implementadas.
	""",

	'maintainer': 'Nuage Peru S.A.C.',
	'category': 'Financial',
	'version': '19.0.1.0.4',
	'license': 'Other proprietary',
	'depends': [
		'solse_pe_cpe_guias',
	],
	'data': [
		'security/ir.model.access.csv',
		'data/sunat_eguide_transport_data.xml',
		'views/company_view.xml',
		'views/stock_picking_type_view.xml',
		'views/stock_view.xml',
		'views/pe_sunat_eguide_transport_view.xml',
		'report/report_guia_transportista.xml',
	],
	'post_init_hook': 'post_init_hook',
	'installable': True,
	'price': 90,
	'currency': 'USD',
}
