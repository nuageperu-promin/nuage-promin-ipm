# -*- coding: utf-8 -*-

from lxml import etree
from io import StringIO, BytesIO
import xmlsec
from collections import OrderedDict
from pysimplesoap.client import SoapClient, SoapFault
import base64
import zipfile
from odoo import _, fields
from odoo.exceptions import UserError
from datetime import datetime
import logging
from tempfile import gettempdir
import hashlib
import requests
import base64
import pytz
from datetime import datetime

import json
_logging = logging.getLogger(__name__)

def convertir_fecha_a_peru(fecha_hora):
	if not fecha_hora:
		return False
	"""
	Función para convertir una fecha y hora a la zona horaria de Perú.

	:param fecha_hora: Objeto datetime con la fecha y hora original.
	:return: Objeto datetime con la fecha y hora convertidas a la zona horaria de Perú.
	"""
	# Obtener la zona horaria de Estados Unidos (donde está el servidor)
	zona_horaria_us = pytz.timezone('America/New_York')

	# Convertir la fecha y hora a la zona horaria de Estados Unidos
	fecha_hora_us = fecha_hora.astimezone(zona_horaria_us)

	# Obtener la zona horaria de Perú
	zona_horaria_pe = pytz.timezone('America/Lima')

	# Convertir la fecha y hora de Estados Unidos a la zona horaria de Perú
	fecha_hora_pe = fecha_hora_us.astimezone(zona_horaria_pe)

	# Extraer la fecha (sin la hora)
	fecha_pe = fecha_hora_pe

	return fecha_pe

class EGuide():
	def __init__(self):
		self._cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
		self._cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
		self._ccts="urn:un:unece:uncefact:documentation:2"
		self._ds="http://www.w3.org/2000/09/xmldsig#"
		self._ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
		self._qdt="urn:oasis:names:specification:ubl:schema:xsd:QualifiedDatatypes-2"
		self._sac="urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1"
		self._udt="urn:un:unece:uncefact:data:specification:UnqualifiedDataTypesSchemaModule:2"
		self._xsi="http://www.w3.org/2001/XMLSchema-instance"
		self._root=None
	   
	def _getX509Template(self, content):
		tag = etree.QName(self._ds, 'Signature')   
		signature=etree.SubElement(content, tag.text, Id="signatureOdoo", nsmap={'ds':tag.namespace})
		tag = etree.QName(self._ds, 'SignedInfo')   
		signed_info=etree.SubElement(signature, tag.text, nsmap={'ds':tag.namespace})
		tag = etree.QName(self._ds, 'CanonicalizationMethod')   
		etree.SubElement(signed_info, tag.text, Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315", nsmap={'ds':tag.namespace})
		tag = etree.QName(self._ds, 'SignatureMethod')   
		etree.SubElement(signed_info, tag.text, Algorithm="http://www.w3.org/2000/09/xmldsig#rsa-sha1", nsmap={'ds':tag.namespace})
		tag = etree.QName(self._ds, 'Reference')   
		reference=etree.SubElement(signed_info, tag.text, URI="", nsmap={'ds':tag.namespace})
		tag = etree.QName(self._ds, 'Transforms')   
		transforms=etree.SubElement(reference, tag.text, nsmap={'ds':tag.namespace})
		tag = etree.QName(self._ds, 'Transform')   
		etree.SubElement(transforms, tag.text, Algorithm="http://www.w3.org/2000/09/xmldsig#enveloped-signature", nsmap={'ds':tag.namespace})
		tag = etree.QName(self._ds, 'DigestMethod')   
		etree.SubElement(reference, tag.text, Algorithm="http://www.w3.org/2000/09/xmldsig#sha1", nsmap={'ds':tag.namespace})
		tag = etree.QName(self._ds, 'DigestValue')   
		etree.SubElement(reference, tag.text, nsmap={'ds':tag.namespace})
		tag = etree.QName(self._ds, 'SignatureValue')   
		etree.SubElement(signature, tag.text, nsmap={'ds':tag.namespace})
		tag = etree.QName(self._ds, 'KeyInfo')   
		key_info=etree.SubElement(signature, tag.text, nsmap={'ds':tag.namespace})
		tag = etree.QName(self._ds, 'X509Data')   
		data=etree.SubElement(key_info, tag.text, nsmap={'ds':tag.namespace})
		tag = etree.QName(self._ds, 'X509SubjectName')   
		etree.SubElement(data, tag.text, nsmap={'ds':tag.namespace})
		tag = etree.QName(self._ds, 'X509Certificate')   
		etree.SubElement(data, tag.text, nsmap={'ds':tag.namespace})
	
	def _getSignature(self, stock_id):
		#es parte de la firma
		tag = etree.QName(self._cac, 'Signature')   
		signature=etree.SubElement(self._root, tag.text, nsmap={'cac':tag.namespace})
		tag = etree.QName(self._cbc, 'ID')   
		etree.SubElement(signature, tag.text, nsmap={'cbc':tag.namespace}).text='IDSignOdoo'
		tag = etree.QName(self._cac, 'SignatoryParty')   
		party=etree.SubElement(signature, tag.text, nsmap={'cac':tag.namespace})
		tag = etree.QName(self._cac, 'PartyIdentification')   
		identification=etree.SubElement(party, tag.text, nsmap={'cac':tag.namespace})
		tag = etree.QName(self._cbc, 'ID')   
		etree.SubElement(identification, tag.text, schemeID= stock_id.company_id.partner_id.doc_type or '-', nsmap={'cbc':tag.namespace}).text=stock_id.company_id.partner_id.doc_number
		tag = etree.QName(self._cac, 'PartyName')   
		name=etree.SubElement(party, tag.text, nsmap={'cac':tag.namespace})
		tag = etree.QName(self._cbc, 'Name')   
		etree.SubElement(name, tag.text, nsmap={'cbc':tag.namespace}).text= etree.CDATA(stock_id.company_id.name)
		tag = etree.QName(self._cac, 'DigitalSignatureAttachment')   
		attachment=etree.SubElement(signature, tag.text, nsmap={'cac':tag.namespace})
		tag = etree.QName(self._cac, 'ExternalReference')   
		reference=etree.SubElement(attachment, tag.text, nsmap={'cac':tag.namespace})
		tag = etree.QName(self._cbc, 'URI')   
		etree.SubElement(reference, tag.text, nsmap={'cbc':tag.namespace}).text="#signatureOdoo" 
		
	def _getCompany(self, stock_id):     
		tag = etree.QName(self._cac, 'DespatchSupplierParty')
		supplier=etree.SubElement(self._root, tag.text, nsmap={'cac':tag.namespace})
		tag = etree.QName(self._cbc, 'CustomerAssignedAccountID')   
		etree.SubElement(supplier, tag.text, schemeID=stock_id.company_id.partner_id.doc_type,
						 nsmap={'cbc':tag.namespace}).text=stock_id.company_id.partner_id.doc_number
		
		tag = etree.QName(self._cac, 'Party')
		party=etree.SubElement(supplier, tag.text, nsmap={'cac':tag.namespace})

		tag = etree.QName(self._cac, 'PartyIdentification')   
		party_identification = etree.SubElement(party, tag.text, nsmap={'cac':tag.namespace})
		tag = etree.QName(self._cbc, 'ID')
		etree.SubElement(party_identification, tag.text, schemeID=stock_id.company_id.partner_id.doc_type, schemeName="Documento de Identidad", schemeAgencyName="PE:SUNAT", schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06", nsmap={'cbc':tag.namespace}).text= stock_id.company_id.partner_id.doc_number

		"""<cac:PartyIdentification>
		<cbc:ID schemeID="6" schemeName="Documento de Identidad" schemeAgencyName="PE:SUNAT" schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06">20000000001</cbc:ID>
	  </cac:PartyIdentification>"""

		tag = etree.QName(self._cac, 'PartyLegalEntity')   
		party_name=etree.SubElement(party, tag.text, nsmap={'cac':tag.namespace})
		tag = etree.QName(self._cbc, 'RegistrationName')   
		comercial_name = stock_id.company_id.partner_id.commercial_name or "-"
		etree.SubElement(party_name, tag.text, nsmap={'cbc':tag.namespace}).text= etree.CDATA(comercial_name.strip()!="-" and comercial_name.strip() or stock_id.company_id.partner_id.name) 
		
	
	def _getUBLVersion(self):
		tag = etree.QName(self._cbc, 'UBLVersionID')   
		etree.SubElement(self._root, tag.text, nsmap={'cbc':tag.namespace}).text='2.1'
		tag = etree.QName(self._cbc, 'CustomizationID')   
		etree.SubElement(self._root, tag.text, nsmap={'cbc':tag.namespace}).text='2.0'

	def _getPartner(self, stock_id):
		parent_id = stock_id.partner_id.parent_id
		partner_id = stock_id.partner_id
		contacto = parent_id or partner_id

		if stock_id.pe_transfer_code in ['02', '04']:
			contacto = stock_id.company_id.partner_id
			partner_id = contacto
			parent_id = contacto

		tag = etree.QName(self._cac, 'DeliveryCustomerParty')   
		customer=etree.SubElement(self._root, tag.text, nsmap={'cac':tag.namespace})
		tag = etree.QName(self._cbc, 'CustomerAssignedAccountID')   
		etree.SubElement(customer, tag.text, schemeID= parent_id and parent_id.doc_type or partner_id.doc_type or '-',
						 nsmap={'cbc':tag.namespace}).text= parent_id and parent_id.doc_number or partner_id.doc_number or '-'
		tag = etree.QName(self._cac, 'Party')  
		party=etree.SubElement(customer, tag.text, nsmap={'cac':tag.namespace})
		tag = etree.QName(self._cac, 'PartyIdentification')   
		party_identification = etree.SubElement(party, tag.text, nsmap={'cac':tag.namespace})
		tag = etree.QName(self._cbc, 'ID')
		if stock_id.pe_transfer_code == '18' and not contacto:
			etree.SubElement(party_identification, tag.text, schemeID=stock_id.company_id.partner_id.doc_type, schemeName="Documento de Identidad", schemeAgencyName="PE:SUNAT", schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06", nsmap={'cbc':tag.namespace}).text= stock_id.company_id.partner_id.doc_number
		else:
			etree.SubElement(party_identification, tag.text, schemeID=contacto.doc_type, schemeName="Documento de Identidad", schemeAgencyName="PE:SUNAT", schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06", nsmap={'cbc':tag.namespace}).text= contacto.doc_number

		"""
		<cac:DeliveryTerms>
		<cac:DeliveryLocation >
		<cac:Address>
		<cbc:StreetName>CALLE NEGOCIOS # 420</cbc:StreetName>
		<cbc:CitySubdivisionName/>
		<cbc:CityName>LIMA</cbc:CityName>
		<cbc:CountrySubentity>LIMA</cbc:CountrySubentity>
		<cbc:CountrySubentityCode>150141</cbc:CountrySubentityCode>
		<cbc:District>SURQUILLO</cbc:District>
		<cac:Country>
		<cbc:IdentificationCode listID="ISO 3166-1" listAgencyName="United Nations Economic
		Commission for Europe" listName="Country">PE</cbc:IdentificationCode>
		</cac:Country>
		</cac:Address>
		</cac:DeliveryLocation >
		</cac:DeliveryTerms>
		"""

		tag = etree.QName(self._cac, 'PartyLegalEntity')   
		entity=etree.SubElement(party, tag.text, nsmap={'cac':tag.namespace})
		name= parent_id and (parent_id.commercial_name!='-' and parent_id.commercial_name or parent_id.name) or (partner_id.commercial_name!='-' and partner_id.commercial_name or partner_id.name) or '-'
		tag = etree.QName(self._cbc, 'RegistrationName')   
		etree.SubElement(entity, tag.text, nsmap={'cbc':tag.namespace}).text= etree.CDATA(name)
	
	def _getSupplier(self, stock_id):
		tag = etree.QName(self._cac, 'SellerSupplierParty')   
		customer=etree.SubElement(self._root, tag.text, nsmap={'cac':tag.namespace})
		tag = etree.QName(self._cbc, 'CustomerAssignedAccountID')   
		etree.SubElement(customer, tag.text, schemeID= stock_id.supplier_id.doc_type or '-',
						 nsmap={'cbc':tag.namespace}).text=stock_id.supplier_id.doc_number or '-'
		
		tag = etree.QName(self._cac, 'Party')  
		party=etree.SubElement(customer, tag.text, nsmap={'cac':tag.namespace})
		tag = etree.QName(self._cac, 'PartyLegalEntity')   
		entity=etree.SubElement(party, tag.text, nsmap={'cac':tag.namespace})
		tag = etree.QName(self._cbc, 'RegistrationName')   
		etree.SubElement(entity, tag.text, nsmap={'cbc':tag.namespace}).text= etree.CDATA(stock_id.supplier_id.commercial_name!='-' and stock_id.supplier_id.commercial_name or stock_id.supplier_id.name or '-')
	
	def _getCarrier(self, stock_id, stage):
		tag = etree.QName(self._cac, 'CarrierParty')   
		customer=etree.SubElement(stage, tag.text, nsmap={'cac':tag.namespace})
		tag = etree.QName(self._cac, 'PartyIdentification')   
		ident=etree.SubElement(customer, tag.text, nsmap={'cac':tag.namespace})
		tag = etree.QName(self._cbc, 'ID')
		etree.SubElement(ident, tag.text, schemeID= stock_id.pe_carrier_id.doc_type or '-',
						 nsmap={'cbc':tag.namespace}).text=stock_id.pe_carrier_id.doc_number or '-'

		tag = etree.QName(self._cac, 'PartyLegalEntity')  
		party=etree.SubElement(customer, tag.text, nsmap={'cac':tag.namespace})
		tag = etree.QName(self._cbc, 'RegistrationName')   
		etree.SubElement(party, tag.text, nsmap={'cbc':tag.namespace}).text= etree.CDATA(stock_id.pe_carrier_id.commercial_name!= '-' and stock_id.pe_carrier_id.commercial_name or stock_id.pe_carrier_id.name or '-')

		# Número de Registro MTC del transportista (campo 44, OBS-4391).
		# Orden UBL 2.1 en cac:PartyLegalEntity: RegistrationName, CompanyID.
		mtc = (stock_id.pe_carrier_id.pe_mtc_number or '').strip().upper()
		if mtc:
			tag = etree.QName(self._cbc, 'CompanyID')
			etree.SubElement(
				party, tag.text, nsmap={'cbc': tag.namespace}
			).text = mtc
	
	def _obtener_documentos_relacionados(self, stock_id):
		"""Genera los nodos cac:AdditionalDocumentReference de la guía.

		Cumple con SUNAT 01/06/2026:
		- Soporta múltiples documentos (One2many).
		- Para tipos 01/03/04/09/12/48/92 incluye IssuerParty con RUC del
		  emisor (ERR-3380, ERR-3382, ERR-3614).
		- Fallback a campos legacy (pe_is_realeted, pe_related_*) cuando
		  no hay registros en el One2many y existen datos sin migrar.
		"""
		tipos_con_emisor = ('01', '03', '04', '09', '12', '48', '92')

		# Construcción de lista unificada: prioriza el One2many; si está vacío
		# y existen datos legacy, los usa como fallback.
		documentos = []
		if stock_id.pe_documento_relacionado_ids:
			for doc in stock_id.pe_documento_relacionado_ids:
				documentos.append({
					'codigo': doc.codigo_documento,
					'numero': doc.numero_documento,
					'emisor': doc.emisor_id,
				})
		elif stock_id.pe_is_realeted and stock_id.pe_related_number:
			documentos.append({
				'codigo': stock_id.pe_related_code,
				'numero': stock_id.pe_related_number,
				'emisor': False,
			})

		for doc in documentos:
			tag = etree.QName(self._cac, 'AdditionalDocumentReference')
			referencia = etree.SubElement(
				self._root, tag.text, nsmap={'cac': tag.namespace}
			)

			tag = etree.QName(self._cbc, 'ID')
			etree.SubElement(
				referencia, tag.text, nsmap={'cbc': tag.namespace}
			).text = doc['numero'] or ''

			tag = etree.QName(self._cbc, 'DocumentTypeCode')
			etree.SubElement(
				referencia, tag.text, nsmap={'cbc': tag.namespace}
			).text = doc['codigo'] or ''

			# IssuerParty con RUC del emisor (ERR-3380/3382/3614)
			emisor = doc.get('emisor')
			if emisor and doc['codigo'] in tipos_con_emisor:
				tag = etree.QName(self._cac, 'IssuerParty')
				issuer = etree.SubElement(
					referencia, tag.text, nsmap={'cac': tag.namespace}
				)

				tag = etree.QName(self._cac, 'PartyIdentification')
				party_id = etree.SubElement(
					issuer, tag.text, nsmap={'cac': tag.namespace}
				)

				tag = etree.QName(self._cbc, 'ID')
				etree.SubElement(
					party_id, tag.text,
					schemeID=emisor.doc_type or '6',
					schemeName='Documento de Identidad',
					schemeAgencyName='PE:SUNAT',
					schemeURI='urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06',
					nsmap={'cbc': tag.namespace}
				).text = emisor.doc_number or '-'

	def _obtener_instrucciones_especiales(self, shipment, stock_id):
		"""Genera nodos cbc:SpecialInstructions con los indicadores SUNAT
		activos (01/06/2026). Cada indicador es un nodo independiente con
		un valor fijo del namespace SUNAT_Envio_*.

		IMPORTANTE: los nombres deben coincidir EXACTAMENTE con los
		listados en la validación SUNAT INFO-3388, de lo contrario el
		XML es rechazado al envío.

		Valores aceptados por SUNAT al 01/06/2026:
		  - SUNAT_Envio_IndicadorTrasladoTotalDAMoDS
		  - SUNAT_Envio_IndicadorTrasladoContenedorManifiestoCarga
		  - SUNAT_Envio_IndicadorTransbordoProgramado
		  - SUNAT_Envio_IndicadorVehiculoConductoresTransp
		  - SUNAT_Envio_IndicadorTrasladoVehiculoM1L
		  - SUNAT_Envio_IndicadorRetornoVehiculoVacio
		  - SUNAT_Envio_IndicadorRetornoVehiculoEnvaseVacio
		"""
		# Sub-régimen 19+92 no emite indicadores especiales
		if stock_id.pe_es_subregimen_19_92:
			return

		indicadores = []
		if stock_id.pe_traslado_total_dam:
			indicadores.append('SUNAT_Envio_IndicadorTrasladoTotalDAMoDS')
		if stock_id.pe_traslado_contenedor_mc:
			indicadores.append('SUNAT_Envio_IndicadorTrasladoContenedorManifiestoCarga')
		if stock_id.pe_transbordo_programado:
			indicadores.append('SUNAT_Envio_IndicadorTransbordoProgramado')
		if stock_id.pe_registro_vehiculos_conductores:
			indicadores.append('SUNAT_Envio_IndicadorVehiculoConductoresTransp')
		if stock_id.pe_vehiculos_m1_l:
			indicadores.append('SUNAT_Envio_IndicadorTrasladoVehiculoM1L')
		if stock_id.pe_retorno_vehiculo_vacio:
			indicadores.append('SUNAT_Envio_IndicadorRetornoVehiculoVacio')
		if stock_id.pe_retorno_envase_vacio:
			indicadores.append('SUNAT_Envio_IndicadorRetornoVehiculoEnvaseVacio')

		for valor in indicadores:
			tag = etree.QName(self._cbc, 'SpecialInstructions')
			etree.SubElement(
				shipment, tag.text, nsmap={'cbc': tag.namespace}
			).text = valor

	def _obtener_unidades_manejo(self, shipment, stock_id):
		"""Genera cac:TransportHandlingUnit con vehículos y contenedores.

		HOTFIX ERR-2566 (publicación SUNAT 01/06/2026):
		La placa del vehículo principal va en cac:TransportEquipment/cbc:ID
		(NO en cac:ShipmentStage/cac:TransportMeans/cac:RoadTransport/
		cbc:LicensePlateID, que SUNAT no valida y trata como informativo).

		Estructura generada:
			<cac:TransportHandlingUnit>
				<!-- Vehículo primero: TransportEquipment precede a Package en
				     el XSD de TransportHandlingUnit (UBL 2.1) -->
				<cac:TransportEquipment>
					<cbc:ID>PLACA_PRINCIPAL</cbc:ID>
					<cac:AttachedTransportEquipment>
						<cbc:ID>PLACA_SECUNDARIA</cbc:ID>
					</cac:AttachedTransportEquipment>
				</cac:TransportEquipment>
				<!-- Contenedores después -->
				<cac:Package>
					<cbc:ID>NUMERO_CONTENEDOR</cbc:ID>
					<cbc:TraceID>NUMERO_PRECINTO</cbc:TraceID>
				</cac:Package>
			</cac:TransportHandlingUnit>

		Reglas de generación del TransportEquipment con placa:
		  - Modalidad 02 (Privado) sin M1/L → obligatorio (ERR-2566)
		  - Modalidad 01 + registro_vehiculos_conductores=True → obligatorio
			(ERR-2566 caso 2)
		  - Modalidad 01 sin registro_vehiculos → no se emite (la placa va
			implícita en cac:CarrierParty del transportista)
		  - M1/L → no se emite (esquema especial)

		Suprimido completamente en sub-régimen 19+92 (ERR-3627, ERR-3628).
		"""
		if stock_id.pe_es_subregimen_19_92:
			return

		# Decidir si corresponde generar TransportEquipment con placa
		emite_placa = self._debe_emitir_placa_en_transport_equipment(stock_id)

		# Si no hay nada que emitir (ni placa ni contenedores), salir
		if not emite_placa and not stock_id.pe_contenedor_ids:
			return

		# UN solo TransportHandlingUnit que agrupa Packages + TransportEquipment
		tag = etree.QName(self._cac, 'TransportHandlingUnit')
		handling = etree.SubElement(
			shipment, tag.text, nsmap={'cac': tag.namespace}
		)

		# 1. TransportEquipment con placa principal (si aplica). En el XSD de
		# cac:TransportHandlingUnit (UBL 2.1) precede a cac:Package; el orden
		# inverso lo rechazaba el homologador con 0306 (19.0.4.21).
		if emite_placa:
			vehiculo_principal = stock_id.pe_fleet_ids.filtered('is_main')[:1] \
				or stock_id.pe_fleet_ids[:1]
			if not vehiculo_principal:
				emite_placa = False
		if emite_placa:

			tag = etree.QName(self._cac, 'TransportEquipment')
			equipment = etree.SubElement(
				handling, tag.text, nsmap={'cac': tag.namespace}
			)
			tag = etree.QName(self._cbc, 'ID')
			etree.SubElement(
				equipment, tag.text, nsmap={'cbc': tag.namespace}
			).text = vehiculo_principal.name or ''

			# TUCE / Certificado de habilitación vehicular (OBS-4399).
			# Solo se admite en modalidad 01 con el 'Indicador de registro de
			# vehículos y conductores del transportista'; en modalidad 01 sin
			# el indicador SUNAT lo rechaza (ERR-3452).
			self._agregar_tuce(equipment, vehiculo_principal, stock_id)

			# Vehículos secundarios (AttachedTransportEquipment) - máx 2 (ERR-4389)
			secundarios = (stock_id.pe_fleet_ids - vehiculo_principal)[:2]
			for veh in secundarios:
				tag = etree.QName(self._cac, 'AttachedTransportEquipment')
				attached = etree.SubElement(
					equipment, tag.text, nsmap={'cac': tag.namespace}
				)
				tag = etree.QName(self._cbc, 'ID')
				etree.SubElement(
					attached, tag.text, nsmap={'cbc': tag.namespace}
				).text = veh.name or ''
				# TUCE del vehículo secundario (OBS-4399 / ERR-3454)
				self._agregar_tuce(attached, veh, stock_id)

		# 2. Packages (contenedores), DESPUÉS de TransportEquipment.
		for contenedor in stock_id.pe_contenedor_ids:
			tag = etree.QName(self._cac, 'Package')
			package = etree.SubElement(
				handling, tag.text, nsmap={'cac': tag.namespace}
			)
			tag = etree.QName(self._cbc, 'ID')
			etree.SubElement(
				package, tag.text, nsmap={'cbc': tag.namespace}
			).text = contenedor.numero_contenedor or ''

			if contenedor.numero_precinto:
				tag = etree.QName(self._cbc, 'TraceID')
				etree.SubElement(
					package, tag.text, nsmap={'cbc': tag.namespace}
				).text = contenedor.numero_precinto


	def _agregar_tuce(self, equipment, linea_vehiculo, stock_id):
		"""Agrega cac:ApplicableTransportMeans/cbc:RegistrationNationalityID.

		Reglas de validación SUNAT publicadas al 20/06/2026, campos 47 y 50:
		  - Modalidad 01 + 'Registro de vehículos y conductores' → SUNAT
			espera el dato (OBS-4399 si falta).
		  - Modalidad 01 SIN ese indicador → prohibido (ERR-3452 vehículo
			principal, ERR-3454 vehículos secundarios).
		  - Modalidad 02 → permitido desde el 01/06/2026 (la restricción de
			ERR-3452/3454 quedó limitada a la modalidad 01), opcional.
		"""
		tuce = (linea_vehiculo.pe_tuce or '').strip().upper()
		if not tuce:
			return
		if stock_id.pe_transport_mode == '01' \
				and not stock_id.pe_registro_vehiculos_conductores:
			return

		tag = etree.QName(self._cac, 'ApplicableTransportMeans')
		medios = etree.SubElement(
			equipment, tag.text, nsmap={'cac': tag.namespace}
		)
		tag = etree.QName(self._cbc, 'RegistrationNationalityID')
		etree.SubElement(
			medios, tag.text, nsmap={'cbc': tag.namespace}
		).text = tuce

	def _debe_emitir_placa_en_transport_equipment(self, stock_id):
		"""Determina si corresponde emitir TransportEquipment/cbc:ID con placa.

		Casos donde SUNAT exige la placa (ERR-2566):
		  - Modalidad 02 sin M1/L
		  - Modalidad 01 con Registro de vehículos/conductores activo

		Delega en stock.picking._emite_vehiculos_conductores() para que la
		regla viva en un solo lugar (misma condición que los conductores).
		"""
		return stock_id._emite_vehiculos_conductores()

	def _obtener_doc_identidad_conductor(self, driver):
		"""Devuelve (schemeID, numero_documento) para el cbc:ID del conductor.

		SUNAT ERR-2571: un conductor (persona natural) NO puede ser
		identificado con RUC (schemeID='6'). El Catálogo 06 SUNAT
		permite para conductor: '1' (DNI), '4' (Carnet extranjería),
		'7' (Pasaporte), 'A' (Cédula diplomática).

		Si el partner del conductor tiene RUC peruano de persona natural
		(inicia con '10' + 8 dígitos DNI + 1 dígito verificador), se
		extrae automáticamente el DNI subyacente y se emite con schemeID='1'.

		Para otros casos (RUC empresarial '20...', tipos no válidos), se
		devuelve lo que hay y SUNAT rechazará. La validación cliente-side
		en validate_eguide() avisa antes del envío.
		"""
		doc_type = driver.doc_type or '1'
		doc_number = (driver.doc_number or '').strip()

		# RUC persona natural → extraer DNI subyacente
		if doc_type == '6' and len(doc_number) == 11 and doc_number.startswith('10'):
			return '1', doc_number[2:10]

		return doc_type, doc_number

	def _obtener_lineas_despacho(self, stock_id):
		"""Genera las cac:DespatchLine.

		Comportamiento normal: una línea por cada stock.move.
		Sub-régimen 19+92 (ERR-3629, ERR-3630): UNA SOLA línea dummy con
		cantidad 1 NIU y descripción genérica. El NetWeightMeasure se
		omite (ERR-3623).
		"""
		if stock_id.pe_es_subregimen_19_92:
			self._generar_linea_dummy(stock_id)
			return

		cont = 1
		for line in stock_id.move_ids:
			tag = etree.QName(self._cac, 'DespatchLine')
			despatch = etree.SubElement(self._root, tag.text, nsmap={'cac': tag.namespace})
			tag = etree.QName(self._cbc, 'ID')
			etree.SubElement(despatch, tag.text, nsmap={'cbc': tag.namespace}).text = str(cont)
			tag = etree.QName(self._cbc, 'DeliveredQuantity')
			etree.SubElement(
				despatch, tag.text,
				unitCode=self._unidad_gre(
					stock_id, line.product_id.uom_id.sunat_code),
				nsmap={'cbc': tag.namespace}
			).text = str(line.quantity)
			tag = etree.QName(self._cac, 'OrderLineReference')
			ref = etree.SubElement(despatch, tag.text, nsmap={'cac': tag.namespace})
			tag = etree.QName(self._cbc, 'LineID')
			etree.SubElement(ref, tag.text, nsmap={'cbc': tag.namespace}).text = str(cont)
			cont += 1

			tag = etree.QName(self._cac, 'Item')
			item = etree.SubElement(despatch, tag.text, nsmap={'cac': tag.namespace})
			tag = etree.QName(self._cbc, 'Description')
			etree.SubElement(
				item, tag.text, nsmap={'cbc': tag.namespace}
			).text = etree.CDATA(line.product_id.name)
			self._agregar_numeracion_dam(item, stock_id)

			tag = etree.QName(self._cac, 'SellersItemIdentification')
			ident = etree.SubElement(item, tag.text, nsmap={'cac': tag.namespace})
			tag = etree.QName(self._cbc, 'ID')
			etree.SubElement(
				ident, tag.text, nsmap={'cbc': tag.namespace}
			).text = line.product_id.default_code or "-"

	def _generar_linea_dummy(self, stock_id):
		"""Genera una sola DespatchLine genérica requerida por XSD UBL
		cuando aplica el sub-régimen 19+92. No representa bienes reales.
		"""
		tag = etree.QName(self._cac, 'DespatchLine')
		despatch = etree.SubElement(self._root, tag.text, nsmap={'cac': tag.namespace})

		tag = etree.QName(self._cbc, 'ID')
		etree.SubElement(despatch, tag.text, nsmap={'cbc': tag.namespace}).text = '1'

		tag = etree.QName(self._cbc, 'DeliveredQuantity')
		etree.SubElement(
			despatch, tag.text,
			unitCode=self._unidad_gre(stock_id, 'NIU'),
			nsmap={'cbc': tag.namespace}
		).text = '1'

		tag = etree.QName(self._cac, 'OrderLineReference')
		ref = etree.SubElement(despatch, tag.text, nsmap={'cac': tag.namespace})
		tag = etree.QName(self._cbc, 'LineID')
		etree.SubElement(ref, tag.text, nsmap={'cbc': tag.namespace}).text = '1'

		tag = etree.QName(self._cac, 'Item')
		item = etree.SubElement(despatch, tag.text, nsmap={'cac': tag.namespace})
		tag = etree.QName(self._cbc, 'Description')
		etree.SubElement(
			item, tag.text, nsmap={'cbc': tag.namespace}
		).text = etree.CDATA('TRASLADO DE MERCANCIA EXTRANJERA')
		self._agregar_numeracion_dam(item, stock_id)

		tag = etree.QName(self._cac, 'SellersItemIdentification')
		ident = etree.SubElement(item, tag.text, nsmap={'cac': tag.namespace})
		tag = etree.QName(self._cbc, 'ID')
		etree.SubElement(
			ident, tag.text, nsmap={'cbc': tag.namespace}
		).text = '-'

	def getGuide(self, stock_id, data):
		xmlns=etree.QName("urn:oasis:names:specification:ubl:schema:xsd:DespatchAdvice-2", 'DespatchAdvice')
		nsmap1=OrderedDict([(None, xmlns.namespace), ('cac', self._cac), ('cbc', self._cbc), ('ccts', self._ccts), 
							('ds', self._ds), ('ext', self._ext), ('qdt', self._qdt), ('sac', self._sac), ('udt', self._udt), 
							('xsi', self._xsi)] )
		self._root=etree.Element(xmlns.text, nsmap=nsmap1)
		tag = etree.QName(self._ext, 'UBLExtensions')
		extensions=etree.SubElement(self._root, tag.text, nsmap={'ext':tag.namespace})
		
		tag = etree.QName(self._ext, 'UBLExtension')
		extension=etree.SubElement(extensions, tag.text, nsmap={'ext':tag.namespace})
		
		tag = etree.QName(self._ext, 'ExtensionContent')
		content=etree.SubElement(extension, tag.text, nsmap={'ext':tag.namespace})
		# X509 Template
		self._getX509Template(content)
		
		self._getUBLVersion()
		tag = etree.QName(self._cbc, 'ID')   
		etree.SubElement(self._root, tag.text, nsmap={'cbc':tag.namespace}).text=stock_id.pe_guide_number or ''
		tag = etree.QName(self._cbc, 'IssueDate')  

		fecha_peru = convertir_fecha_a_peru(stock_id.date_done)
		etree.SubElement(self._root, tag.text, nsmap={'cbc':tag.namespace}).text=str(stock_id.pe_date_issue) # datetime.strptime(stock_id.min_date, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d")
		
		tag = etree.QName(self._cbc, 'IssueTime')   
		etree.SubElement(self._root, tag.text, nsmap={'cbc':tag.namespace}).text= fecha_peru.strftime("%H:%M:%S")
		
		tag = etree.QName(self._cbc, 'DespatchAdviceTypeCode')   
		etree.SubElement(self._root, tag.text, nsmap={'cbc':tag.namespace}).text='09'
		if stock_id.note:
			tag = etree.QName(self._cbc, 'Note')   
			etree.SubElement(self._root, tag.text, nsmap={'cbc':tag.namespace}).text=stock_id.note or '-'
			
		# Documentos relacionados (cac:AdditionalDocumentReference)
		# Soporta múltiples documentos y agrega IssuerParty cuando aplica
		# (SUNAT 01/06/2026: ERR-3380, ERR-3382, ERR-3614).
		self._obtener_documentos_relacionados(stock_id)
		
		self._getSignature(stock_id)
		
		self._getCompany(stock_id)
		
		self._getPartner(stock_id)
		
		if stock_id.supplier_id:
			self._getSupplier(stock_id)
		
		tag = etree.QName(self._cac, 'Shipment')
		shipment = etree.SubElement(self._root, tag.text, nsmap={'cac':tag.namespace})
		
		tag = etree.QName(self._cbc, 'ID')
		etree.SubElement(shipment, tag.text, nsmap={'cbc':tag.namespace}).text = '1'
		
		tag = etree.QName(self._cbc, 'HandlingCode')
		etree.SubElement(shipment, tag.text, nsmap={'cbc':tag.namespace}).text = stock_id.pe_transfer_code

		if stock_id.pe_transfer_code == '13':
			tag = etree.QName(self._cbc, 'HandlingInstructions')
			etree.SubElement(shipment, tag.text, nsmap={'cbc':tag.namespace}).text = stock_id.motivo_transferencia or "Otro motivo"

		# SUNAT 01/06/2026 - en sub-régimen 19+92 NO se envían los tags
		# Information, GrossWeightMeasure ni TotalTransportHandlingUnitQuantity
		# (ERR-3624, ERR-3625, ERR-3626).
		if not stock_id.pe_es_subregimen_19_92:
			# Sustento de la diferencia del Peso bruto total de la carga
			# respecto al peso de los ítems seleccionados.
			if stock_id.pe_transfer_code in ['08', '09']:
				tag = etree.QName(self._cbc, 'Information')
				etree.SubElement(shipment, tag.text, nsmap={'cbc':tag.namespace}).text = etree.CDATA(stock_id.origin or '')

			tag = etree.QName(self._cbc, 'GrossWeightMeasure')
			etree.SubElement(shipment, tag.text, unitCode="KGM",
							 nsmap={'cbc':tag.namespace}).text = str(stock_id.pe_gross_weight)

			# Cantidad de bultos: se envía cuando motivo 08 lo requiere, o
			# cuando el usuario consigna pe_unit_quantity > 0 sin contenedores
			# (caso ERR-3631/3632).
			tiene_contenedor = bool(stock_id.pe_contenedor_ids)
			# 19.0.4.20: con contenedor nunca se emite el tag, tampoco en el
			# motivo 08 (antes salía con valor 0 y chocaba con ERR-3621).
			if not tiene_contenedor and (
				stock_id.pe_transfer_code == '08'
				or (stock_id.pe_unit_quantity and stock_id.pe_unit_quantity > 0)
			):
				tag = etree.QName(self._cbc, 'TotalTransportHandlingUnitQuantity')
				etree.SubElement(shipment, tag.text, nsmap={'cbc':tag.namespace}).text = str(stock_id.pe_unit_quantity)

		# SUNAT 01/06/2026 - cbc:SpecialInstructions (indicadores)
		# Va DESPUÉS de TotalTransportHandlingUnitQuantity y ANTES de
		# SplitConsignmentIndicator según orden UBL 2.1.
		self._obtener_instrucciones_especiales(shipment, stock_id)

		tag = etree.QName(self._cbc, 'SplitConsignmentIndicator')
		etree.SubElement(shipment, tag.text, nsmap={'cbc':tag.namespace}).text = stock_id.pe_is_programmed and 'true' or 'false'
		
		
		# ShipmentStage
		tag = etree.QName(self._cac, 'ShipmentStage')
		stage= etree.SubElement(shipment, tag.text, nsmap={'cac':tag.namespace})
		
		tag = etree.QName(self._cbc, 'ID')
		etree.SubElement(stage, tag.text, nsmap={'cbc':tag.namespace}).text = '1'
		
		tag = etree.QName(self._cbc, 'TransportModeCode')
		etree.SubElement(stage, tag.text, nsmap={'cbc':tag.namespace}).text = stock_id.pe_transport_mode
		
		tag = etree.QName(self._cac, 'TransitPeriod')
		period = etree.SubElement(stage, tag.text, nsmap={'cac':tag.namespace})
		tag = etree.QName(self._cbc, 'StartDate')
		fecha_hecha = convertir_fecha_a_peru(stock_id.scheduled_date if stock_id.scheduled_date else stock_id.date_done)
		etree.SubElement(period, tag.text, nsmap={'cbc':tag.namespace}).text = fecha_hecha.strftime('%Y-%m-%d')
																				
		
		
		if stock_id.pe_transport_mode=='01':
			self._getCarrier(stock_id, stage)
		else:
			# Modalidad 02-Privado: TransportMeans (vehículo principal).
			# Se prioriza el marcado is_main; si no hay marcado, se usa el primero.
			vehiculo_principal = stock_id.pe_fleet_ids.filtered('is_main')[:1] \
				or stock_id.pe_fleet_ids[:1]
			if vehiculo_principal:
				tag = etree.QName(self._cac, 'TransportMeans')
				transport = etree.SubElement(stage, tag.text, nsmap={'cac': tag.namespace})
				tag = etree.QName(self._cac, 'RoadTransport')
				road = etree.SubElement(transport, tag.text, nsmap={'cac': tag.namespace})
				tag = etree.QName(self._cbc, 'LicensePlateID')
				etree.SubElement(road, tag.text,
								 nsmap={'cbc': tag.namespace}).text = vehiculo_principal.name

		# SUNAT 01/06/2026 - cac:LoadingTransportEvent
		# Tag UBL: cac:Shipment/cac:ShipmentStage/cac:LoadingTransportEvent/cbc:OccurrenceDate
		# Obligatorio para modalidad 01-Público (ERR-3617, ERR-3618, ERR-3619).
		# IMPORTANTE: en UBL 2.1 debe ir DESPUÉS de TransportMeans/CarrierParty
		# y ANTES de DriverPerson para no violar el orden de la secuencia XSD.
		if stock_id.pe_transport_mode == '01' and stock_id.pe_delivery_date:
			tag = etree.QName(self._cac, 'LoadingTransportEvent')
			loading_event = etree.SubElement(stage, tag.text, nsmap={'cac': tag.namespace})
			tag = etree.QName(self._cbc, 'OccurrenceDate')
			etree.SubElement(
				loading_event, tag.text, nsmap={'cbc': tag.namespace}
			).text = stock_id.pe_delivery_date.strftime('%Y-%m-%d')

		# Conductores. Se agregan DESPUÉS del LoadingTransportEvent para
		# respetar el orden de la secuencia UBL 2.1.
		#
		# SUNAT (reglas publicadas al 20/06/2026, campos 52 al 58):
		#   - Modalidad 02-Privado sin M1/L ............ obligatorio (ERR-3357)
		#   - Modalidad 01-Público + 'Registro de vehículos y conductores
		#     del transportista' sin M1/L .............. obligatorio (ERR-3357)
		#   - Modalidad 01-Público sin ese indicador ... prohibido (ERR-3455)
		#   - M1/L verdadero ........................... prohibido (ERR-3455)
		if stock_id._emite_vehiculos_conductores():
			# Un único conductor 'Principal' (ERR-3358); el resto 'Secundario'
			# hasta un máximo de 2 (campo 56).
			principal = stock_id.pe_fleet_ids.filtered('is_main')[:1] \
				or stock_id.pe_fleet_ids[:1]
			conductores = principal + (stock_id.pe_fleet_ids - principal)[:2]

			for line in conductores:
				tag = etree.QName(self._cac, 'DriverPerson')
				customer=etree.SubElement(stage, tag.text, nsmap={'cac':tag.namespace})

				# HOTFIX ERR-2571: el conductor NO puede tener RUC (schemeID='6').
				# Si el partner trae RUC persona natural ('10' + DNI + dígito),
				# se extrae el DNI automáticamente.
				doc_type_conductor, doc_number_conductor = \
					self._obtener_doc_identidad_conductor(line.driver_id)

				tag = etree.QName(self._cbc, 'ID')
				etree.SubElement(customer, tag.text, schemeID=doc_type_conductor,
								 nsmap={'cbc':tag.namespace}).text=doc_number_conductor

				nombres = line.driver_id.name.split(" ")
				nombres = nombres[0]
				apellidos = line.driver_id.name.replace(nombres, "")

				tag = etree.QName(self._cbc, 'FirstName')   
				etree.SubElement(customer, tag.text, nsmap={'cbc':tag.namespace}).text= nombres

				tag = etree.QName(self._cbc, 'FamilyName')   
				etree.SubElement(customer, tag.text, nsmap={'cbc':tag.namespace}).text= apellidos

				# ERR-3358: solo puede existir un conductor 'Principal'.
				tag = etree.QName(self._cbc, 'JobTitle')
				etree.SubElement(
					customer, tag.text, nsmap={'cbc': tag.namespace}
				).text = (line == principal) and "Principal" or "Secundario"

				tag = etree.QName(self._cac, 'IdentityDocumentReference')   
				iden_doc_ref=etree.SubElement(customer, tag.text, nsmap={'cac':tag.namespace})
				tag = etree.QName(self._cbc, 'ID')   
				etree.SubElement(iden_doc_ref, tag.text, nsmap={'cbc':tag.namespace}).text = line.driver_id.pe_driver_license or '-'
		
		
		tag = etree.QName(self._cac, 'Delivery')
		delivery = etree.SubElement(shipment, tag.text, nsmap={'cac':tag.namespace})
		# Direccion recojo
		contacto_envio = stock_id.partner_id
		if stock_id.picking_type_id.code == 'internal' and stock_id.almacen_destino:
			contacto_origen = stock_id.almacen_destino.partner_id

		if stock_id.picking_type_id.code == 'incoming':
			contacto_origen = stock_id.company_id.partner_id

		if stock_id.pe_transfer_code == '02':
			contacto_envio = stock_id.company_id.partner_id

		if stock_id.pe_transfer_code == '18' and not contacto_envio:
			tag = etree.QName(self._cac, 'DeliveryAddress')   
			address=etree.SubElement(delivery, tag.text, nsmap={'cac':tag.namespace})
			tag = etree.QName(self._cbc, 'ID')    
			etree.SubElement(address, tag.text, nsmap={'cbc':tag.namespace}).text=''
			tag = etree.QName(self._cac, 'AddressLine')   
			line_address=etree.SubElement(address, tag.text, nsmap={'cac':tag.namespace})
			tag = etree.QName(self._cbc, 'Line')    
			etree.SubElement(line_address, tag.text, nsmap={'cbc':tag.namespace}).text=''
		else:
			tag = etree.QName(self._cac, 'DeliveryAddress')   
			address=etree.SubElement(delivery, tag.text, nsmap={'cac':tag.namespace})
			tag = etree.QName(self._cbc, 'ID')    
			etree.SubElement(address, tag.text, nsmap={'cbc':tag.namespace}).text=contacto_envio.l10n_pe_district.code
			tag = etree.QName(self._cac, 'AddressLine')   
			line_address=etree.SubElement(address, tag.text, nsmap={'cac':tag.namespace})
			tag = etree.QName(self._cbc, 'Line')    
			etree.SubElement(line_address, tag.text, nsmap={'cbc':tag.namespace}).text=len(contacto_envio.street)>100 and contacto_envio.street[0:100] or contacto_envio.street

		# Direccion partida
		contacto_origen = stock_id.company_id.partner_id
		

		if stock_id.picking_type_id.code == 'internal' and stock_id.almacen_origen:
			contacto_origen = stock_id.almacen_origen.partner_id

		if stock_id.picking_type_id.code == 'outgoing' and stock_id.almacen_origen:
			contacto_origen = stock_id.almacen_origen.partner_id

		if stock_id.picking_type_id.code == 'incoming':
			contacto_origen = stock_id.partner_id

		if stock_id.pe_transfer_code == '02':
			contacto_origen = stock_id.partner_id

		tag = etree.QName(self._cac, 'Despatch')   
		address=etree.SubElement(delivery, tag.text, nsmap={'cac':tag.namespace})
		tag = etree.QName(self._cac, 'DespatchAddress')   
		despatch_address=etree.SubElement(address, tag.text, nsmap={'cac':tag.namespace})
		tag = etree.QName(self._cbc, 'ID')    
		etree.SubElement(despatch_address, tag.text, nsmap={'cbc':tag.namespace}).text=contacto_origen.l10n_pe_district.code
		tag = etree.QName(self._cac, 'AddressLine')   
		line_address=etree.SubElement(despatch_address, tag.text, nsmap={'cac':tag.namespace})
		tag = etree.QName(self._cbc, 'Line')    
		etree.SubElement(line_address, tag.text, nsmap={'cbc':tag.namespace}).text=len(contacto_origen.street)>100 and contacto_origen.street[0:100] or contacto_origen.street

		
		# SUNAT 01/06/2026 - cac:TransportHandlingUnit con contenedores
		# Se suprime completamente en sub-régimen 19+92 (ERR-3627, ERR-3628).
		# Va DESPUÉS de cac:Delivery según orden UBL 2.1.
		self._obtener_unidades_manejo(shipment, stock_id)
			
		tag = etree.QName(self._cac, 'OriginAddress')   
		oaddress=etree.SubElement(shipment, tag.text, nsmap={'cac':tag.namespace})
		tag = etree.QName(self._cbc, 'ID')
		   
		etree.SubElement(oaddress, tag.text, nsmap={'cbc':tag.namespace}).text=stock_id.picking_type_id.warehouse_id.partner_id.l10n_pe_district.code
		tag = etree.QName(self._cbc, 'StreetName')   
		etree.SubElement(oaddress, tag.text, nsmap={'cbc':tag.namespace}).text=len(stock_id.picking_type_id.warehouse_id.partner_id.street or "-")>100 and stock_id.picking_type_id.warehouse_id.partner_id.street[0:100] or stock_id.picking_type_id.warehouse_id.partner_id.street or "-" 
		
		# Puerto/Aeropuerto de embarque (R.S. 123-2022, campos 71-73).
		# cac:FirstArrivalPortLocation va DESPUÉS de OriginAddress según el
		# orden de cac:Shipment en UBL 2.1. Obligatorio en motivo 09
		# (error 3369) y condicional en 08 (error 3365); cbc:ID lleva el
		# código an3 del Catálogo 63 (puertos) o 64 (aeropuertos),
		# cbc:LocationTypeCode el tipo 1/2 y cbc:Name el nombre.
		if stock_id.pe_transfer_code in ('08', '09') and stock_id.pe_puerto_id:
			puerto = stock_id.pe_puerto_id
			tag = etree.QName(self._cac, 'FirstArrivalPortLocation')
			port_location = etree.SubElement(
				shipment, tag.text, nsmap={'cac': tag.namespace})
			tag = etree.QName(self._cbc, 'ID')
			etree.SubElement(
				port_location, tag.text,
				schemeAgencyName='PE:SUNAT',
				schemeName='Puertos' if puerto.tipo == '1' else 'Aeropuertos',
				schemeURI='urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo'
						  + ('63' if puerto.tipo == '1' else '64'),
				nsmap={'cbc': tag.namespace}).text = puerto.codigo
			tag = etree.QName(self._cbc, 'LocationTypeCode')
			etree.SubElement(
				port_location, tag.text,
				nsmap={'cbc': tag.namespace}).text = puerto.tipo
			tag = etree.QName(self._cbc, 'Name')
			etree.SubElement(
				port_location, tag.text,
				nsmap={'cbc': tag.namespace}).text = puerto.name[:200]

		# SUNAT 01/06/2026 - DespatchLines
		# En sub-régimen 19+92 se genera UNA SOLA línea dummy (ERR-3629, 3630)
		# que es requerida por XSD pero no representa bienes reales.
		# El NetWeightMeasure se suprime en esta línea (ERR-3623).
		self._obtener_lineas_despacho(stock_id)
				
		xml_str = etree.tostring(self._root, pretty_print=True, xml_declaration = True, encoding='utf-8', standalone=False)
		return xml_str

	# Catálogo 03 → Catálogo 65: unidades ADUANERAS de la GRE.
	# Cuando la guía va con DAM o DS (motivos 08/09 con documento
	# relacionado 50/52), SUNAT valida cbc:DeliveredQuantity/@unitCode
	# contra el Catálogo 65 —códigos propios de aduanas— y rechaza con
	# 3446 los del Catálogo 03 (NIU incluido). Se mapean los usuales y
	# el resto cae a 'U' (Unidad), que es el genérico del 65.
	CATALOGO_03_A_65 = {
		'NIU': 'U', 'ZZ': 'U', 'C62': 'PZA', 'KGM': 'KG', 'GRM': 'GR',
		'TNE': 'TM', 'LBR': 'LB', 'ONZ': 'OZ', 'LTR': 'L', 'MLT': 'ML',
		'GLL': 'GAL', 'MTR': 'M', 'CMT': 'CM', 'MMT': 'MM', 'MTK': 'M2',
		'MTQ': 'M3', 'FOT': 'PS', 'FTK': 'PS2', 'FTQ': 'PS3',
		'YRD': 'YD', 'YDK': 'YD2', 'INH': 'PUL', 'PR': '2U',
		'DZN': '12U', 'GRO': 'GRU', 'CEN': 'U2', 'MLL': 'MLL',
		'SET': 'SET', 'KT': 'KIT', 'BX': 'CAJ', 'BG': 'BLS',
		'PK': 'PAQ', 'BO': 'BOT', 'CT': 'CRT', 'DR': 'CIL',
		'RO': 'ROL', 'SA': 'SAC', 'TU': 'TUB', 'KWH': 'KWH',
	}

	def _agregar_numeracion_dam(self, item, stock_id):
		"""Numeración de la DAM/DS como propiedad del ítem (concepto 7021).

		Regla 3427: en motivos 08/09/19 SIN el indicador de traslado total
		de la DAM, cada línea debe consignar la numeración de la DAM o DS
		en cac:AdditionalItemProperty con código de concepto 7021, y el
		valor debe coincidir con el documento relacionado tipo 50/52.
		Con el indicador de traslado total, el bloque no es exigible y no
		se emite.
		"""
		if stock_id.pe_traslado_total_dam:
			return
		if stock_id.pe_transfer_code not in ('08', '09', '19'):
			return
		documento = stock_id.pe_documento_relacionado_ids.filtered(
			lambda d: d.codigo_documento in ('50', '52'))[:1]
		if not documento:
			return
		tag = etree.QName(self._cac, 'AdditionalItemProperty')
		propiedad = etree.SubElement(
			item, tag.text, nsmap={'cac': tag.namespace})
		tag = etree.QName(self._cbc, 'Name')
		etree.SubElement(
			propiedad, tag.text, nsmap={'cbc': tag.namespace}
		).text = 'Numeracion de la DAM o DS'
		tag = etree.QName(self._cbc, 'NameCode')
		etree.SubElement(
			propiedad, tag.text,
			listName='Propiedad del item',
			listAgencyName='PE:SUNAT',
			listURI='urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo55',
			nsmap={'cbc': tag.namespace}).text = '7021'
		tag = etree.QName(self._cbc, 'Value')
		etree.SubElement(
			propiedad, tag.text, nsmap={'cbc': tag.namespace}
		).text = documento.numero_documento

	def _contexto_aduanero(self, stock_id):
		"""Verdadero cuando la guía traslada mercancía de una DAM o DS."""
		if stock_id.pe_transfer_code not in ('08', '09'):
			return False
		return bool(stock_id.pe_documento_relacionado_ids.filtered(
			lambda d: d.codigo_documento in ('50', '52')))

	def _unidad_gre(self, stock_id, codigo_catalogo_03):
		codigo = codigo_catalogo_03 or 'NIU'
		if self._contexto_aduanero(stock_id):
			return self.CATALOGO_03_A_65.get(codigo, 'U')
		return codigo

	def getGuideVoided(self, data):
		xmlns=etree.QName("urn:oasis:names:specification:ubl:schema:xsd:DespatchAdvice-2", 'DespatchAdvice')
		nsmap1=OrderedDict([(None, xmlns.namespace), ('cac', self._cac), ('cbc', self._cbc), ('ccts', self._ccts), 
							('ds', self._ds), ('ext', self._ext), ('qdt', self._qdt), ('sac', self._sac), ('udt', self._udt), 
							('xsi', self._xsi)] )
		self._root=etree.Element(xmlns.text, nsmap=nsmap1)
		tag = etree.QName(self._ext, 'UBLExtensions')
		extensions=etree.SubElement(self._root, tag.text, nsmap={'ext':tag.namespace})
		
		tag = etree.QName(self._ext, 'UBLExtension')
		extension=etree.SubElement(extensions, tag.text, nsmap={'ext':tag.namespace})
		
		tag = etree.QName(self._ext, 'ExtensionContent')
		content=etree.SubElement(extension, tag.text, nsmap={'ext':tag.namespace})
		# X509 Template
		self._getX509Template(content)
		
		self._getUBLVersion()
		tag = etree.QName(self._cbc, 'ID')   
		etree.SubElement(self._root, tag.text, nsmap={'cbc':tag.namespace}).text= data.name
		tag = etree.QName(self._cbc, 'IssueDate')   
		fecha_peru = convertir_fecha_a_peru(stock_id.date_done)
		etree.SubElement(self._root, tag.text, nsmap={'cbc':tag.namespace}).text= fecha_peru.date # datetime.strptime(stock_id.min_date, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d")
		
		tag = etree.QName(self._cbc, 'DespatchAdviceTypeCode')   
		etree.SubElement(self._root, tag.text, nsmap={'cbc':tag.namespace}).text='09'
		#if data.note:
		#    tag = etree.QName(self._cbc, 'Note')   
		#    etree.SubElement(self._root, tag.text, nsmap={'cbc':tag.namespace}).text= data.note or '-'
		
		for line in data.voided_ids:
			tag = etree.QName(self._cac, 'OrderReference')   
			reference=etree.SubElement(self._root, tag.text, nsmap={'cac':tag.namespace})
			tag = etree.QName(self._cbc, 'ID')   
			etree.SubElement(reference, tag.text, nsmap={'cbc':tag.namespace}).text=line.pe_guide_number
			tag = etree.QName(self._cbc, 'OrderTypeCode')   
			etree.SubElement(reference, tag.text, name=u"GUIA DE REMISIÓN", 
							 nsmap={'cbc':tag.namespace}).text='09'
			
		self._getSignature(data)
		
		self._getCompany(data)
		
				
		xml_str = etree.tostring(self._root, pretty_print=True, xml_declaration = True, encoding='utf-8', standalone=False)
		return xml_str

	
class Document(object):

	def __init__(self):
		self._xml = None
		self._type = None
		self._document_name = None
		self._client = None
		self._response = None
		self._zip_file = None
		self._response_status = None
		self._response_data = None
		self._ticket = None
		self.in_memory_data = BytesIO()
		self.in_memory_zip = zipfile.ZipFile(self.in_memory_data, "w", zipfile.ZIP_DEFLATED, False)

	def writetofile(self, filename, filecontent):
		self.in_memory_zip.writestr(filename, filecontent)

	def prepare_zip(self):
		self._zip_filename = '{}.zip'.format(self._document_name)
		xml_filename = '{}.xml'.format(self._document_name)
		self.writetofile(xml_filename, self._xml)
		for zfile in self.in_memory_zip.filelist:
			zfile.create_system = 0
		self.in_memory_zip.close()

	def send(self):
		if self._type=="sync":
			self._zip_file = base64.b64encode(self.in_memory_data.getvalue())
			self._response_status, self._response = self._client.send_bill(self._zip_filename, self._zip_file)
		elif self._type=="ticket":
			self._response_status, self._response = self._client.get_status(self._ticket)
		elif self._type=="status":
			self._response_status, self._response = self._client.get_status_cdr(self._document_name)
		else:
			self._zip_file = base64.b64encode(self.in_memory_data.getvalue())
			self._response_status, self._response = self._client.send_bill(self._zip_filename, self._zip_file)
	
	def process_response(self):
		if self._response is None or not self._response_status:
			return
		if self._type == 'sync':
			self._response_data = self._response['numTicket']
		elif self._type == 'ticket':
			if 'arcCdr' not in self._response:
				texto = "No se pudo parsear: %s" % str(self._response)
				raise UserError(texto)
			self._response_data = self._response['arcCdr']
		elif self._type == 'status':
			self._response_data = self._response['arcCdr']
		else:
			self._response_data = self._response['numTicket']
	
	def process(self, document_name, type, xml, client):
		self._xml = xml
		self._type = type
		self._document_name = document_name
		self._client = client
		
		self.prepare_zip()
		self.send()
		self.process_response()
		return self._zip_file, self._response_status, self._response, self._response_data
	
	@staticmethod
	def get_response(file, name):
		zf = zipfile.ZipFile(BytesIO(base64.b64decode(file)))
		datos = False
		try:
			datos = zf.open(name).read()
		except:
			datos = False

		if not datos:
			nombres = name.split("-")
			ultimo = nombres[-1].split(".")
			extencion = ultimo[1]
			ultimo = int(ultimo[0])
			nombres.pop()
			name = "-".join(nombres)
			name = "%s-%s.%s" % (name, str(ultimo), extencion)
			try:
				datos = zf.open(name).read()
			except:
				datos = False

		return datos

	def get_status(self, ticket, client):
		self._type="ticket"
		self._ticket = ticket
		self._client=client
		self.send()
		self.process_response()
		return self._response_status, self._response, self._response_data
	
	def get_status_cdr(self, document_name, client):
		self._type="status"
		self._client = client
		self._document_name = document_name
		self.send()
		return self._response_status, self._response, self._response_data


class Client(object):

	def __init__(self, ruc, username, password, client_id, client_secret, url):
		self._type=type
		self._ruc = ruc
		self._username = "%s%s" %(ruc,username)
		self._password = password
		self._client_id = client_id
		self._client_secret = client_secret
		self._token = False
		self._url = url
		level = logging.DEBUG
		logging.basicConfig(level=level)
		_logging.setLevel(level)
		self._connect()

	def _connect(self):
		url_base = self._url
		if url_base == 'https://api-cpe.sunat.gob.pe':
			url_base = 'https://api-seguridad.sunat.gob.pe'

		endpoint = "%s/v1/clientessol/%s/oauth2/token/" % (url_base, self._client_id)
		#beta
		# https://gre-test.nubefact.com/v1/clientessol/<client_id>/oauth2/token
		headers = {
			"Content-Type": "application/x-www-form-urlencoded",
		}
		datos_json = {
			'grant_type': 'password',
			'scope': 'https://api-cpe.sunat.gob.pe',
			'client_id': self._client_id,
			'client_secret': self._client_secret,
			'username': self._username,
			'password': self._password,
		}
		datos_peticion = requests.post(endpoint, data=datos_json, headers=headers)
		if datos_peticion.status_code == 200:
			datos = datos_peticion.json()
			token = datos['access_token']
			self._token = token
		else:
			raise UserError("No se pudo obtener el tocken para la conexion con el API")
			self._token = False

	def send_bill(self, filename, content_file):
		nombre = filename.split(".")[0]
		res=nombre.split("-")
		#endpoint = "https://api-cpe.sunat.gob.pe/v1/contribuyente/gem/comprobantes/{numRucEmisor}-{codCpe}-{numSerie}-{numCpe}"
		url_base = self._url
		endpoint = "%s/v1/contribuyente/gem/comprobantes/%s-%s-%s-%s" % (url_base, res[0], res[1], res[2], res[3])
		# beta
		# https://gre-test.nubefact.com/v1/contribuyente/gem/comprobantes/{numRucEmisor}-{codCpe}-{numSerie}-{numCpe}
		headers = {
			"Content-Type": "application/json",
			"Accept": "application/json",
			"Authorization": "Bearer %s" % self._token,
		}
		m = hashlib.sha256()
		m.update(base64.b64decode(content_file))
		hashZip = m.hexdigest()

		#{"numTicket":"6913f876-123a-4c01-8aba-73b2a311a6af","fecRecepcion":"2026-12-29T10:27:59"}

		datos_archivo = {
			"nomArchivo": filename,
			"arcGreZip": str(content_file, "utf-8"),
			"hashZip": hashZip
		}
		datos_json = {
			"archivo": datos_archivo,
		}
		datos_json = json.dumps(datos_json)
		datos_peticion = requests.post(endpoint, data=datos_json, headers=headers)
		if datos_peticion.status_code == 200:
			datos = json.loads(datos_peticion.text)
			rpt = [datos_peticion.status_code, datos]
			return rpt
		else:
			return [False, False]

	def send_summary(self, filename, content_file):
		params = {
			'fileName': filename,
			'contentFile': str(content_file, "utf-8")
		}
		return self._call_service('sendSummary', params)

	def get_status(self, ticket_code):
		#endpoint = "https://api-cpe.sunat.gob.pe/v1/contribuyente/gem/comprobantes/{numRucEmisor}-{codCpe}-{numSerie}-{numCpe}"
		url_base = self._url
		endpoint = "%s/v1/contribuyente/gem/comprobantes/envios/%s" % (url_base, ticket_code)
		# beta
		# https://gre-test.nubefact.com/v1/contribuyente/gem/comprobantes/envios/{numTicket}
		headers = {
			"Content-Type": "application/json",
			"Accept": "application/json",
			"Authorization": "Bearer %s" % self._token,
		}
		datos_json = {}
		datos_json = json.dumps(datos_json)
		datos_peticion = requests.get(endpoint, data=datos_json, headers=headers)
		if datos_peticion.status_code == 200:
			datos = json.loads(datos_peticion.text)
			return [datos['codRespuesta'], datos]
		else:
			return [False, False]

	def get_status_cdr(self, document_name):
		res=document_name.split("-")
		params = {
			'rucComprobante': res[0],
			'tipoComprobante': res[1],
			'serieComprobante': res[2],
			'numeroComprobante': res[3]
		}
		return self._call_service('getStatusCdr', params)

def get_document(self):
	if self.type=="sync":
		xml = EGuide().getGuide(self.picking_ids[0], self)
	else:
		xml = EGuide().getGuideVoided(self)
	return xml

def get_sign_document(xml, key_file, crt_file):
	xml_iofile=BytesIO(xml.encode('utf-8'))
	root=etree.parse(xml_iofile).getroot()
	signature_node = xmlsec.tree.find_node(root, xmlsec.Node.SIGNATURE)
	assert signature_node is not None
	assert signature_node.tag.endswith(xmlsec.Node.SIGNATURE)
	ctx = xmlsec.SignatureContext()
	key = xmlsec.Key.from_memory(key_file, xmlsec.KeyFormat.PEM)
	assert key is not None
	key.load_cert_from_memory(crt_file, xmlsec.KeyFormat.PEM)
	ctx.key = key
	assert ctx.key is not None
	# Sign the template.
	ctx.sign(signature_node)
	return etree.tostring(root,  pretty_print=True, xml_declaration = True, encoding='utf-8', standalone=False)

def get_ticket_status(ticket, client):
	client = Client(**client)
	return Document().get_status(ticket, client)

def get_response(data):
	return Document().get_response(**data)

def get_status_cdr(send_number, client):
	client = Client(**client)
	return Document().get_status_cdr(send_number, client)

def send_sunat_eguide(client, document):
	client = Client(**client)    
	document['client']=client    
	return Document().process(**document)

