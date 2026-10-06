# -*- coding: utf-8 -*-
"""Definición de los casos del laboratorio de guías.

Cada caso es un diccionario con:
  - codigo / nombre / tipo_guia ('09' | '31') / descripcion
  - resultado_esperado: 'aceptada' (la validación local pasa y el XML se
	genera). 'rechazo_local' sigue soportado por el modelo pero los casos
	precargados son todos aceptables: un rechazo esperado confunde al
	cliente que usa el laboratorio como demostración.
  - datos: valores que el sembrador aplica sobre el picking; las claves
	especiales (vehiculos, contenedores, documentos, remitente,
	destinatario, subcontratador, pagador_tercero) las resuelve el sembrador
  - verificaciones: lista de (descripcion, xpath, esperado) sobre el XML.
	`esperado` es un str (igualdad con el primer nodo/atributo), una lista
	(igualdad con todos los text()) o None (el xpath debe existir).

Los valores esperados están escritos a mano desde las hojas
Guía-Remitente2_0 y Guía-Transportista2_0, no derivados del generador.
"""

# RUC ficticios con dígito verificador válido (módulo 11).
RUC_REMITENTE = '20512345671'
RUC_DESTINATARIO = '20601234565'
RUC_SUBCONTRATADOR = '20487654320'
RUC_TRANSPORTISTA_PUBLICO = '20554321098'
DNI_CONDUCTOR_1 = '45678912'
DNI_CONDUCTOR_2 = '87654321'
DNI_TERCERO = '12345678'
# RUC persona natural del conductor 2: '10' + DNI + dv (para ERR-2571).
RUC_CONDUCTOR_2 = '10876543210'

CAC = 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2'
CBC = 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'
NS = {'cac': CAC, 'cbc': CBC}


def _grr_base(**extra):
	datos = {
		'pe_transfer_code': '01',
		'pe_transport_mode': '02',
		'pe_gross_weight': 120.5,
		'vehiculos': [('QA1234', 'conductor_1', True)],
	}
	datos.update(extra)
	return datos


def _grt_base(**extra):
	datos = {
		'remitente': RUC_REMITENTE,
		'destinatario': RUC_DESTINATARIO,
		'pe_gross_weight': 1500.0,
		'pe_grt_peso_unidad': 'KGM',
		'pe_grt_pagador_flete': 'remitente',
		'pe_grt_anotacion': 'CARGA GENERAL PALETIZADA',
		'vehiculos': [('QA1234', 'conductor_1', True)],
	}
	datos.update(extra)
	return datos


CASOS = [
	# ------------------------------------------------------------------
	# Guía de Remisión Remitente (09)
	# ------------------------------------------------------------------
	{
		'codigo': 'GRR-01',
		'nombre': 'Venta, transporte privado, un vehículo',
		'tipo_guia': '09',
		'descripcion': 'Motivo 01, modalidad 02, bultos completados por Odoo.',
		'resultado_esperado': 'aceptada',
		'datos': _grr_base(),
		'verificaciones': [
			('Tipo 09', '/*/cbc:DespatchAdviceTypeCode/text()', '09'),
			('Motivo 01', '//cac:Shipment/cbc:HandlingCode/text()', '01'),
			('Placa en TransportEquipment', '//cac:TransportHandlingUnit/cac:TransportEquipment/cbc:ID/text()', 'QA1234'),
			('Conductor con DNI', '//cac:DriverPerson/cbc:ID/@schemeID', '1'),
			('JobTitle Principal', '//cac:DriverPerson/cbc:JobTitle/text()', ['Principal']),
			('Bultos > 0', '//cac:Shipment/cbc:TotalTransportHandlingUnitQuantity/text()', None),
		],
	},
	{
		'codigo': 'GRR-02',
		'nombre': 'Contenedor con precinto, bultos en cero (fix 19.0.4.19)',
		'tipo_guia': '09',
		'descripcion': 'Hasta 19.0.4.18 caía en ERR-3621 porque validate_eguide() '
					   'rellenaba los bultos con 1 antes de validar contenedores.',
		'resultado_esperado': 'aceptada',
		'datos': _grr_base(contenedores=[('TCKU1234567', 'PRE-001')]),
		'verificaciones': [
			('Contenedor en Package', '//cac:TransportHandlingUnit/cac:Package/cbc:ID/text()', 'TCKU1234567'),
			('Precinto en TraceID', '//cac:TransportHandlingUnit/cac:Package/cbc:TraceID/text()', 'PRE-001'),
			('Sin tag de bultos', '//cac:Shipment/cbc:TotalTransportHandlingUnitQuantity', []),
			('Orden XSD: vehículo antes que contenedor', 'ORDEN:cac:TransportHandlingUnit', ['TransportEquipment', 'Package']),
		],
	},
	{
		'codigo': 'GRR-03',
		'nombre': 'Transporte público con transportista',
		'tipo_guia': '09',
		'descripcion': 'Modalidad 01 sin registro de vehículos: CarrierParty y '
					   'fecha de entrega; sin placa ni conductor.',
		'resultado_esperado': 'aceptada',
		'datos': _grr_base(
			pe_transport_mode='01', vehiculos=[],
			transportista=RUC_TRANSPORTISTA_PUBLICO, pe_delivery_date='hoy'),
		'verificaciones': [
			('Modalidad 01', '//cac:ShipmentStage/cbc:TransportModeCode/text()', '01'),
			('CarrierParty con RUC', '//cac:ShipmentStage/cac:CarrierParty/cac:PartyIdentification/cbc:ID/text()', RUC_TRANSPORTISTA_PUBLICO),
			('Sin DriverPerson', '//cac:DriverPerson', []),
			('Sin placa', '//cac:TransportEquipment/cbc:ID', []),
			('Fecha de entrega', '//cac:LoadingTransportEvent/cbc:OccurrenceDate/text()', None),
		],
	},
	{
		'codigo': 'GRR-04',
		'nombre': 'Importación con DAM, traslado total y contenedor (ERR-3631)',
		'tipo_guia': '09',
		'descripcion': 'Motivo 08 + doc 50 + indicador de traslado total + '
					   'contenedor con precinto, partiendo del puerto del Callao. '
					   'La lectura anterior del ERR-3631 lo rechazaba; el Excel '
					   '20/06/2026 lo admite.',
		'resultado_esperado': 'aceptada',
		'datos': _grr_base(
			pe_transfer_code='08', pe_traslado_total_dam=True,
			# 3365: en importación el punto de partida es el puerto; su ubigeo
			# debe coincidir (3364), así que se siembra un almacén en Callao.
			puerto='CLL', almacen_ubigeo='070101',
			documentos=[('50', '118-2026-10-123456', RUC_REMITENTE)],
			contenedores=[('TCKU7654321', 'PRE-002')]),
		'verificaciones': [
			('Motivo 08', '//cac:Shipment/cbc:HandlingCode/text()', '08'),
			('Puerto de desembarque (3365)', '//cac:FirstArrivalPortLocation/cbc:ID/text()', 'CLL'),
			('Ubigeo de partida = puerto (3364)', '//cac:Despatch/cac:DespatchAddress/cbc:ID/text()', '070101'),
			('Indicador traslado total', '//cac:Shipment/cbc:SpecialInstructions/text()', ['SUNAT_Envio_IndicadorTrasladoTotalDAMoDS']),
			('DAM como doc relacionado', '//cac:AdditionalDocumentReference/cbc:ID/text()', '118-2026-10-123456'),
			('Tipo 50', '//cac:AdditionalDocumentReference/cbc:DocumentTypeCode/text()', '50'),
			('Contenedor', '//cac:Package/cbc:ID/text()', 'TCKU7654321'),
			('Sin bultos', '//cac:Shipment/cbc:TotalTransportHandlingUnitQuantity', []),
			('Sin 7021 (traslado total)', "//cac:AdditionalItemProperty/cbc:NameCode[text()='7021']", []),
		],
	},
	# ------------------------------------------------------------------
	# Guía de Remisión Transportista (31)
	# ------------------------------------------------------------------
	{
		'codigo': 'GRT-01',
		'nombre': 'GRT mínima',
		'tipo_guia': '31',
		'descripcion': 'Remitente, destinatario, un vehículo con conductor DNI, '
					   'pagador del flete remitente.',
		'resultado_esperado': 'aceptada',
		'datos': _grt_base(),
		'verificaciones': [
			('Tipo 31', '/*/cbc:DespatchAdviceTypeCode/text()', '31'),
			('Shipment ID fijo', '//cac:Shipment/cbc:ID/text()', 'SUNAT_Envio'),
			('Emisor = transportista (compañía)', '//cac:DespatchSupplierParty/cbc:CustomerAssignedAccountID/text()', 'RUC_COMPANIA'),
			('Remitente en DespatchParty', '//cac:Despatch/cac:DespatchParty/cac:PartyIdentification/cbc:ID/text()', RUC_REMITENTE),
			('Destinatario', '//cac:DeliveryCustomerParty/cac:Party/cac:PartyIdentification/cbc:ID/text()', RUC_DESTINATARIO),
			('Placa obligatoria (35)', '//cac:TransportHandlingUnit/cac:TransportEquipment/cbc:ID/text()', 'QA1234'),
			('Sin placa en RoadTransport (v17)', '//cac:RoadTransport/cbc:LicensePlateID', []),
			('Pagador remitente', '//cac:Shipment/cbc:SpecialInstructions/text()', ['SUNAT_Envio_IndicadorPagadorFlete_Remitente']),
			('Sin doc que ampare: detalle de bienes (3435)', '//cac:DespatchLine/cbc:ID/text()', ['1']),
			('Cantidad del bien', '//cac:DespatchLine/cbc:DeliveredQuantity/text()', None),
			('Sin línea 0 (3458)', "//cac:DespatchLine[cbc:ID='0']", []),
			('Sin SellerSupplierParty', '//cac:SellerSupplierParty', []),
			('Peso KGM', '//cac:Shipment/cbc:GrossWeightMeasure/@unitCode', 'KGM'),
			('Orden en Shipment', 'ORDEN:cac:Shipment', ['ID', 'GrossWeightMeasure', 'SpecialInstructions', 'ShipmentStage', 'Delivery', 'TransportHandlingUnit']),
		],
	},
	{
		'codigo': 'GRT-02',
		'nombre': 'GRT completa: 2 vehículos, subcontratador, pagador tercero, MTC, TUCE',
		'tipo_guia': '31',
		'descripcion': 'Escenario completo del handoff v18. El conductor 2 tiene RUC '
					   'persona natural y debe salir como DNI (ERR-2571). La GRE '
					   'física 0001-123 (serie numérica) ampara los bienes: línea 0 '
					   '(reglas 3458 / 4429).',
		'resultado_esperado': 'aceptada',
		'datos': _grt_base(
			vehiculos=[('QA1234', 'conductor_1', True, 'TUCE1234567890'),
					   ('QA5678', 'conductor_2_ruc', False, '')],
			pe_grt_registro_mtc='MTC0012345',
			pe_grt_traslado_total=True,
			pe_grt_subcontratado=True, subcontratador=RUC_SUBCONTRATADOR,
			pe_grt_pagador_flete='tercero', pagador_tercero=DNI_TERCERO,
			pe_grt_peso_unidad='TNE', pe_gross_weight=1.5,
			documentos=[('09', '0001-123', RUC_REMITENTE)]),
		'verificaciones': [
			('Vehículo secundario', '//cac:AttachedTransportEquipment/cbc:ID/text()', ['QA5678']),
			('TUCE del principal', '//cac:TransportEquipment/cac:ApplicableTransportMeans/cbc:RegistrationNationalityID/text()', ['TUCE1234567890']),
			('Conductores Principal/Secundario', '//cac:DriverPerson/cbc:JobTitle/text()', ['Principal', 'Secundario']),
			('ERR-2571: conductor 2 como DNI', '//cac:DriverPerson[2]/cbc:ID/@schemeID', '1'),
			('ERR-2571: DNI extraído del RUC', '//cac:DriverPerson[2]/cbc:ID/text()', DNI_CONDUCTOR_2),
			('Registro MTC', '//cac:ShipmentStage/cac:CarrierParty/cac:PartyLegalEntity/cbc:CompanyID/text()', 'MTC0012345'),
			('Consignment ID', '//cac:Consignment/cbc:ID/text()', 'SUNAT_Envio'),
			('Subcontratador', '//cac:LogisticsOperatorParty/cac:PartyIdentification/cbc:ID/text()', RUC_SUBCONTRATADOR),
			('Pagador tercero', '//cac:OriginatorCustomerParty/cac:Party/cac:PartyIdentification/cbc:ID/text()', DNI_TERCERO),
			('Indicadores', '//cac:Shipment/cbc:SpecialInstructions/text()',
			 ['SUNAT_Envio_IndicadorTrasladoTotal', 'SUNAT_Envio_IndicadorTrasporteSubcontratado', 'SUNAT_Envio_IndicadorPagadorFlete_Tercero']),
			('Peso TNE', '//cac:Shipment/cbc:GrossWeightMeasure/@unitCode', 'TNE'),
			('Doc relacionado con IssuerParty', '//cac:AdditionalDocumentReference/cac:IssuerParty/cac:PartyIdentification/cbc:ID/text()', RUC_REMITENTE),
			('GRE física ampara: línea 0 con anotación (3458/4429)', '//cac:DespatchLine/cbc:ID/text()', ['0']),
			('Anotación en Description', '//cac:DespatchLine/cac:Item/cbc:Description/text()', 'CARGA GENERAL PALETIZADA'),
			('Orden raíz', 'ORDEN:/*', ['UBLExtensions', 'UBLVersionID', 'CustomizationID', 'ID', 'IssueDate', 'IssueTime', 'DespatchAdviceTypeCode', 'AdditionalDocumentReference', 'Signature', 'DespatchSupplierParty', 'DeliveryCustomerParty', 'OriginatorCustomerParty', 'Shipment', 'DespatchLine']),
			('Orden en ShipmentStage', 'ORDEN:cac:ShipmentStage', ['TransitPeriod', 'CarrierParty', 'DriverPerson', 'DriverPerson']),
		],
	},
	{
		'codigo': 'GRT-03',
		'nombre': 'GRT de exportación con DAM (régimen 40) y detalle de bienes',
		'tipo_guia': '31',
		'descripcion': 'Documento relacionado 50 con régimen 40 (único admitido junto '
					   'al 10 en la GRT, ERR-3441). Sin traslado total, el detalle de '
					   'bienes es obligatorio (3435). Pagador del flete: remitente.',
		'resultado_esperado': 'aceptada',
		'datos': _grt_base(
			documentos=[('50', '118-2026-40-123456', RUC_REMITENTE)],
			pe_grt_peso_unidad='KGM', pe_gross_weight=2350.0),
		'verificaciones': [
			('DAM como doc relacionado', '//cac:AdditionalDocumentReference/cbc:ID/text()', '118-2026-40-123456'),
			('Tipo 50', '//cac:AdditionalDocumentReference/cbc:DocumentTypeCode/text()', '50'),
			('Detalle de bienes obligatorio (3435)', '//cac:DespatchLine/cbc:ID/text()', ['1']),
			('Sin línea 0', "//cac:DespatchLine[cbc:ID='0']", []),
			('Unidad catálogo 03', '//cac:DespatchLine/cbc:DeliveredQuantity/@unitCode', 'NIU'),
			('Pagador remitente', '//cac:Shipment/cbc:SpecialInstructions/text()', ['SUNAT_Envio_IndicadorPagadorFlete_Remitente']),
		],
	},
	{
		'codigo': 'GRT-04',
		'nombre': 'GRT con factura física, traslado total y autorización especial',
		'tipo_guia': '31',
		'descripcion': 'Factura con serie numérica (física) + indicador de traslado '
					   'total: SUNAT espera la línea 0 con la anotación (3458/4429). '
					   'Autorización especial MTC en cac:AgentParty (campo 11) en vez '
					   'del Registro MTC; retorno de vehículo con envases vacíos.',
		'resultado_esperado': 'aceptada',
		'datos': _grt_base(
			documentos=[('01', '0001-456', RUC_REMITENTE)],
			pe_grt_traslado_total=True,
			pe_grt_autorizacion_numero='AUT-2026-000123',
			pe_grt_autorizacion_entidad='06',
			pe_grt_retorno_envase_vacio=True,
			pe_grt_anotacion='ENVASES RETORNABLES DE VIDRIO'),
		'verificaciones': [
			('Factura física como doc relacionado', '//cac:AdditionalDocumentReference/cbc:ID/text()', '0001-456'),
			('Línea 0 con anotación (3458/4429)', '//cac:DespatchLine/cbc:ID/text()', ['0']),
			('Anotación', '//cac:DespatchLine/cac:Item/cbc:Description/text()', 'ENVASES RETORNABLES DE VIDRIO'),
			('Autorización especial en AgentParty', '//cac:CarrierParty/cac:AgentParty/cac:PartyLegalEntity/cbc:CompanyID/text()', 'AUT-2026-000123'),
			('Entidad autorizadora (schemeID)', '//cac:CarrierParty/cac:AgentParty/cac:PartyLegalEntity/cbc:CompanyID/@schemeID', '06'),
			('Sin Registro MTC (3353)', '//cac:CarrierParty/cac:PartyLegalEntity/cbc:CompanyID', []),
			('Indicadores', '//cac:Shipment/cbc:SpecialInstructions/text()',
			 ['SUNAT_Envio_IndicadorTrasladoTotal', 'SUNAT_Envio_IndicadorRetornoVehiculoEnvaseVacio', 'SUNAT_Envio_IndicadorPagadorFlete_Remitente']),
		],
	},
]
