# -*- coding: utf-8 -*-
#
# Generador del XML UBL 2.1 de la Guía de Remisión Electrónica
# Transportista (DespatchAdviceTypeCode = 31).
#
# La clase hereda de EGuide (solse_pe_cpe_guias) para reutilizar sin
# duplicar: plantilla X509, firma, DespatchSupplierParty (que en la GRT es
# el transportista emisor), documentos relacionados con IssuerParty
# (01/06/2026) y el helper ERR-2571 de documento de conductor.
#
# Fuente de la estructura: hoja "Guía-Transportista2_0" de las
# validaciones GRE publicadas por SUNAT. El número entre paréntesis en
# los comentarios es el N° de campo de esa hoja.

from collections import OrderedDict

from lxml import etree

from odoo.addons.solse_pe_cpe_guias.models.eguide import (
	EGuide,
	convertir_fecha_a_peru,
)

import logging

_logging = logging.getLogger(__name__)


# Valores exactos aceptados por SUNAT en cbc:SpecialInstructions de la GRT.
# Cualquier variación en el texto produce rechazo al envío.
INDICADORES_GRT = {
	'traslado_total': 'SUNAT_Envio_IndicadorTrasladoTotal',
	'retorno_envase_vacio': 'SUNAT_Envio_IndicadorRetornoVehiculoEnvaseVacio',
	'retorno_vehiculo_vacio': 'SUNAT_Envio_IndicadorRetornoVehiculoVacio',
	'transbordo_programado': 'SUNAT_Envio_IndicadorTransbordoProgramado',
	'subcontratado': 'SUNAT_Envio_IndicadorTrasporteSubcontratado',
	'pagador_remitente': 'SUNAT_Envio_IndicadorPagadorFlete_Remitente',
	'pagador_subcontratador': 'SUNAT_Envio_IndicadorPagadorFlete_Subcontratador',
	'pagador_tercero': 'SUNAT_Envio_IndicadorPagadorFlete_Tercero',
}


class EGuideTransport(EGuide):
	"""Constructor del DespatchAdvice tipo 31."""

	# ------------------------------------------------------------------
	# Utilidades comunes
	# ------------------------------------------------------------------
	def _prefijo_namespace(self, namespace):
		"""Devuelve el prefijo que corresponde a cada namespace UBL."""
		return {
			self._cac: 'cac',
			self._cbc: 'cbc',
			self._ext: 'ext',
			self._sac: 'sac',
			self._ds: 'ds',
		}.get(namespace, 'cbc')

	def _crear_nodo(self, padre, namespace, nombre, texto=None, cdata=False, **atributos):
		"""Azúcar sintáctico para etree.SubElement con QName."""
		tag = etree.QName(namespace, nombre)
		nodo = etree.SubElement(
			padre, tag.text,
			nsmap={self._prefijo_namespace(namespace): tag.namespace},
			**atributos
		)
		if texto is not None:
			nodo.text = etree.CDATA(texto) if cdata else texto
		return nodo

	def _nombre_partner(self, partner):
		"""Razón social o nombre comercial del contacto, sin el placeholder '-'."""
		if not partner:
			return '-'
		comercial = (partner.commercial_name or '').strip()
		if comercial and comercial != '-':
			return comercial
		return (partner.name or '-').strip()

	def _direccion_partner(self, partner):
		"""Dirección truncada a 100 caracteres como exige SUNAT."""
		calle = (partner.street or '-') if partner else '-'
		return calle[:100]

	def _ubigeo_partner(self, partner):
		if partner and partner.l10n_pe_district:
			return partner.l10n_pe_district.code or ''
		return ''

	def _identificar_party(self, padre, partner, con_atributos=True):
		"""cac:PartyIdentification/cbc:ID + cac:PartyLegalEntity/cbc:RegistrationName."""
		identificacion = self._crear_nodo(padre, self._cac, 'PartyIdentification')
		atributos = {'schemeID': partner.doc_type or '-'}
		if con_atributos:
			atributos.update({
				'schemeName': 'Documento de Identidad',
				'schemeAgencyName': 'PE:SUNAT',
				'schemeURI': 'urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06',
			})
		self._crear_nodo(
			identificacion, self._cbc, 'ID',
			texto=partner.doc_number or '-', **atributos
		)
		entidad = self._crear_nodo(padre, self._cac, 'PartyLegalEntity')
		self._crear_nodo(
			entidad, self._cbc, 'RegistrationName',
			texto=self._nombre_partner(partner), cdata=True
		)

	# ------------------------------------------------------------------
	# Bloques propios de la GRT
	# ------------------------------------------------------------------
	def _obtener_destinatario(self, stock_id):
		"""cac:DeliveryCustomerParty - destinatario (campos 18 y 19)."""
		destinatario = stock_id.pe_grt_destinatario_id
		customer = self._crear_nodo(self._root, self._cac, 'DeliveryCustomerParty')
		self._crear_nodo(
			customer, self._cbc, 'CustomerAssignedAccountID',
			texto=destinatario.doc_number or '-',
			schemeID=destinatario.doc_type or '-'
		)
		party = self._crear_nodo(customer, self._cac, 'Party')
		self._identificar_party(party, destinatario)

	def _obtener_pagador_flete(self, stock_id):
		"""cac:OriginatorCustomerParty - solo cuando el flete lo paga un
		tercero (campos 62 y 63)."""
		if stock_id.pe_grt_pagador_flete != 'tercero':
			return
		tercero = stock_id.pe_grt_pagador_tercero_id
		if not tercero:
			return
		originator = self._crear_nodo(self._root, self._cac, 'OriginatorCustomerParty')
		party = self._crear_nodo(originator, self._cac, 'Party')
		self._identificar_party(party, tercero)

	def _obtener_indicadores_grt(self, shipment, stock_id):
		"""cbc:SpecialInstructions de la GRT (campos 53 a 58).

		Cada indicador es un nodo independiente y no puede repetirse. El
		indicador de pagador de flete es obligatorio (campo 58) y admite
		un único valor de los tres posibles.
		"""
		indicadores = []
		if stock_id.pe_grt_traslado_total:
			indicadores.append(INDICADORES_GRT['traslado_total'])
		if stock_id.pe_grt_retorno_envase_vacio:
			indicadores.append(INDICADORES_GRT['retorno_envase_vacio'])
		if stock_id.pe_grt_retorno_vehiculo_vacio:
			indicadores.append(INDICADORES_GRT['retorno_vehiculo_vacio'])
		if stock_id.pe_grt_transbordo_programado:
			indicadores.append(INDICADORES_GRT['transbordo_programado'])
		if stock_id.pe_grt_subcontratado:
			indicadores.append(INDICADORES_GRT['subcontratado'])
		if stock_id.pe_grt_pagador_flete:
			indicadores.append(
				INDICADORES_GRT['pagador_%s' % stock_id.pe_grt_pagador_flete]
			)

		for valor in indicadores:
			self._crear_nodo(shipment, self._cbc, 'SpecialInstructions', texto=valor)

	def _obtener_subcontratador(self, shipment, stock_id):
		"""cac:Consignment - empresa que subcontrata (campos 60 y 61).

		Obligatorio cuando existe el indicador de transporte subcontratado.
		Va ANTES de cac:ShipmentStage según la secuencia XSD de cac:Shipment.
		"""
		if not stock_id.pe_grt_subcontratado or not stock_id.pe_grt_subcontratador_id:
			return
		subcontratador = stock_id.pe_grt_subcontratador_id
		consignment = self._crear_nodo(shipment, self._cac, 'Consignment')
		# Identificador obligatorio de valor fijo (campo 60).
		self._crear_nodo(consignment, self._cbc, 'ID', texto='SUNAT_Envio')
		operador = self._crear_nodo(consignment, self._cac, 'LogisticsOperatorParty')
		self._identificar_party(operador, subcontratador)

	def _obtener_transportista_stage(self, stage, stock_id):
		"""cac:ShipmentStage/cac:CarrierParty - Registro MTC (campo 10) y
		autorización especial vía cac:AgentParty (campo 11).

		Ambos son condicionales; el nodo solo se emite si hay algún dato.
		SUNAT rechaza (3353) si se consigna más de una autorización.
		"""
		registro_mtc = (stock_id.pe_grt_registro_mtc or '').strip()
		numero_autorizacion = (stock_id.pe_grt_autorizacion_numero or '').strip()
		entidad_autorizadora = (stock_id.pe_grt_autorizacion_entidad or '').strip()

		if not registro_mtc and not numero_autorizacion:
			return

		carrier = self._crear_nodo(stage, self._cac, 'CarrierParty')

		# La autorización especial (AgentParty) precede a PartyLegalEntity
		# en la secuencia XSD de cac:Party.
		if numero_autorizacion:
			agente = self._crear_nodo(carrier, self._cac, 'AgentParty')
			entidad = self._crear_nodo(agente, self._cac, 'PartyLegalEntity')
			atributos = {}
			if entidad_autorizadora:
				atributos['schemeID'] = entidad_autorizadora
			self._crear_nodo(
				entidad, self._cbc, 'CompanyID',
				texto=numero_autorizacion, **atributos
			)

		if registro_mtc:
			entidad = self._crear_nodo(carrier, self._cac, 'PartyLegalEntity')
			self._crear_nodo(entidad, self._cbc, 'CompanyID', texto=registro_mtc)

	def _obtener_conductores(self, stage, stock_id):
		"""cac:ShipmentStage/cac:DriverPerson (campos 41 a 48).

		El vehículo marcado como principal aporta el conductor Principal;
		el resto van como Secundario con un tope de 2 (campo 45).
		El documento de identidad pasa por el helper ERR-2571 heredado.
		"""
		principal = stock_id.pe_fleet_ids.filtered('is_main')[:1] \
			or stock_id.pe_fleet_ids[:1]
		secundarios = (stock_id.pe_fleet_ids - principal)[:2]

		for linea in (principal + secundarios):
			if not linea.driver_id:
				continue
			conductor = linea.driver_id
			nodo = self._crear_nodo(stage, self._cac, 'DriverPerson')

			# ERR-2571: el conductor no puede identificarse con RUC.
			tipo_doc, numero_doc = self._obtener_doc_identidad_conductor(conductor)
			self._crear_nodo(
				nodo, self._cbc, 'ID', texto=numero_doc, schemeID=tipo_doc
			)

			nombre_completo = (conductor.name or '').strip()
			partes = nombre_completo.split(" ")
			nombres = partes[0] if partes else '-'
			apellidos = nombre_completo.replace(nombres, "", 1).strip() or '-'

			self._crear_nodo(nodo, self._cbc, 'FirstName', texto=nombres)
			self._crear_nodo(nodo, self._cbc, 'FamilyName', texto=apellidos)
			self._crear_nodo(
				nodo, self._cbc, 'JobTitle',
				texto='Principal' if linea in principal else 'Secundario'
			)

			licencia = self._crear_nodo(nodo, self._cac, 'IdentityDocumentReference')
			self._crear_nodo(
				licencia, self._cbc, 'ID',
				texto=conductor.pe_driver_license or '-'
			)

	def _obtener_vehiculos(self, shipment, stock_id):
		"""cac:Shipment/cac:TransportHandlingUnit (campos 35 a 40).

		CORRECCIÓN RESPECTO A LA v17: en la GRT la placa es OBLIGATORIA en
		cac:TransportEquipment/cbc:ID. El tag
		ShipmentStage/TransportMeans/RoadTransport/LicensePlateID que
		emitía la v17 no forma parte de la estructura de la 31.

		Los vehículos secundarios (máx. 2) van en
		cac:AttachedTransportEquipment. La TUCE/certificado de habilitación
		vehicular se emite en cac:ApplicableTransportMeans (campos 36 y 39)
		con el helper _agregar_tuce del módulo base.
		"""
		principal = stock_id.pe_fleet_ids.filtered('is_main')[:1] \
			or stock_id.pe_fleet_ids[:1]
		if not principal:
			return
		secundarios = (stock_id.pe_fleet_ids - principal)[:2]

		handling = self._crear_nodo(shipment, self._cac, 'TransportHandlingUnit')
		equipment = self._crear_nodo(handling, self._cac, 'TransportEquipment')
		self._crear_nodo(equipment, self._cbc, 'ID', texto=principal.name or '')
		# TUCE: helper del base (campo pe_tuce de pe.stock.fleet); con
		# pe_transport_mode = '02' lo emite siempre que exista.
		self._agregar_tuce(equipment, principal, stock_id)

		for vehiculo in secundarios:
			adjunto = self._crear_nodo(
				equipment, self._cac, 'AttachedTransportEquipment'
			)
			self._crear_nodo(adjunto, self._cbc, 'ID', texto=vehiculo.name or '')
			self._agregar_tuce(adjunto, vehiculo, stock_id)

	def _obtener_puntos_traslado(self, shipment, stock_id):
		"""cac:Shipment/cac:Delivery - llegada (32, 33) y partida (16, 17,
		29, 30).

		Según la secuencia XSD de cac:Delivery, DeliveryAddress va antes
		que Despatch. El remitente (DespatchParty) cuelga de Despatch.
		"""
		delivery = self._crear_nodo(shipment, self._cac, 'Delivery')

		# Punto de llegada
		llegada = stock_id.pe_grt_punto_llegada_id or stock_id.pe_grt_destinatario_id
		direccion = self._crear_nodo(delivery, self._cac, 'DeliveryAddress')
		self._crear_nodo(
			direccion, self._cbc, 'ID', texto=self._ubigeo_partner(llegada)
		)
		linea = self._crear_nodo(direccion, self._cac, 'AddressLine')
		self._crear_nodo(
			linea, self._cbc, 'Line', texto=self._direccion_partner(llegada)
		)

		# Punto de partida + remitente
		despacho = self._crear_nodo(delivery, self._cac, 'Despatch')
		partida = stock_id.pe_grt_punto_partida_id or stock_id.pe_grt_remitente_id
		direccion = self._crear_nodo(despacho, self._cac, 'DespatchAddress')
		self._crear_nodo(
			direccion, self._cbc, 'ID', texto=self._ubigeo_partner(partida)
		)
		linea = self._crear_nodo(direccion, self._cac, 'AddressLine')
		self._crear_nodo(
			linea, self._cbc, 'Line', texto=self._direccion_partner(partida)
		)

		remitente = self._crear_nodo(despacho, self._cac, 'DespatchParty')
		self._identificar_party(remitente, stock_id.pe_grt_remitente_id)

	# Línea 0 (anotación) vs detalle de bienes. Hoja Guía-Transportista2_0:
	#   3458 la línea 0 es ERROR salvo que exista: 09 con serie NUMÉRICA
	#        (guía física), 82, 01/04 con serie numérica + traslado total,
	#        o 03/12/48 + traslado total.
	#   4429 en esos mismos casos SUNAT observa si falta la línea 0.
	#   3435 el detalle con cantidad > 0 es obligatorio si hay 01/03/04/12/
	#        48/50/52 sin traslado total, o si no hay ninguno de 01/03/04/
	#        12/48/50/52/09/82.
	#   4434 con 09 electrónica, 01/04 electrónicos + total o 50/52 + total,
	#        el detalle con cantidad solo se OBSERVA (nunca es error).
	# Primer envío al homologador (19.0.1.0.1) confirmó que con 09
	# electrónica la línea 0 se rechaza: la lectura invertida venía de v18.
	@staticmethod
	def _serie_numerica(numero):
		serie = (numero or '').strip().split('-')[0]
		return bool(serie) and serie[0].isdigit()

	def _admite_linea_anotacion(self, stock_id):
		"""Verdadero cuando SUNAT espera la línea única ID 0 (3458 / 4429)."""
		total = bool(stock_id.pe_grt_traslado_total)
		for documento in stock_id.pe_documento_relacionado_ids:
			codigo = documento.codigo_documento
			numerica = self._serie_numerica(documento.numero_documento)
			if codigo == '82' or (codigo == '09' and numerica):
				return True
			if total and ((codigo in ('01', '04') and numerica) or codigo in ('03', '12', '48')):
				return True
		return False

	def _exige_detalle_bienes(self, stock_id):
		"""Verdadero cuando el detalle con cantidad > 0 es obligatorio (3435)."""
		codigos = set(stock_id.pe_documento_relacionado_ids.mapped('codigo_documento'))
		if codigos & {'01', '03', '04', '12', '48', '50', '52'} and not stock_id.pe_grt_traslado_total:
			return True
		return not (codigos & {'01', '03', '04', '12', '48', '50', '52', '09', '82'})

	def _obtener_linea_anotacion_grt(self, stock_id):
		"""cac:DespatchLine única con cbc:ID '0' y la anotación (campo 51).

		Solo es válida cuando los bienes están amparados por otro documento;
		en cualquier otro caso SUNAT rechaza con 3458 ("el número de item
		debe ser mayor a cero").
		"""
		despatch = self._crear_nodo(self._root, self._cac, 'DespatchLine')
		self._crear_nodo(despatch, self._cbc, 'ID', texto='0')
		self._crear_nodo(
			despatch, self._cbc, 'DeliveredQuantity', texto='1', unitCode='NIU'
		)
		referencia = self._crear_nodo(despatch, self._cac, 'OrderLineReference')
		self._crear_nodo(referencia, self._cbc, 'LineID', texto='0')

		item = self._crear_nodo(despatch, self._cac, 'Item')
		anotacion = (stock_id.pe_grt_anotacion or '').strip() or '-'
		self._crear_nodo(
			item, self._cbc, 'Description', texto=anotacion[:500], cdata=True
		)
		identificacion = self._crear_nodo(
			item, self._cac, 'SellersItemIdentification'
		)
		self._crear_nodo(identificacion, self._cbc, 'ID', texto='-')

	def _obtener_lineas_bienes_grt(self, stock_id):
		"""cac:DespatchLine por cada bien transportado (campos 21 a 28):
		obligatorias cuando ningún documento relacionado ampara el detalle
		(3435, 2580, 2883, 2781). La unidad sale del catálogo 03 del UoM."""
		numero = 1
		for movimiento in stock_id.move_ids:
			cantidad = movimiento.quantity or movimiento.product_uom_qty
			if not cantidad or cantidad <= 0:
				continue
			despatch = self._crear_nodo(self._root, self._cac, 'DespatchLine')
			self._crear_nodo(despatch, self._cbc, 'ID', texto=str(numero))
			self._crear_nodo(
				despatch, self._cbc, 'DeliveredQuantity',
				texto=str(cantidad),
				unitCode=movimiento.product_id.uom_id.sunat_code or 'NIU'
			)
			referencia = self._crear_nodo(despatch, self._cac, 'OrderLineReference')
			self._crear_nodo(referencia, self._cbc, 'LineID', texto=str(numero))
			item = self._crear_nodo(despatch, self._cac, 'Item')
			descripcion = (movimiento.description_picking or movimiento.product_id.name or '-').strip()
			self._crear_nodo(
				item, self._cbc, 'Description', texto=descripcion[:500], cdata=True
			)
			identificacion = self._crear_nodo(item, self._cac, 'SellersItemIdentification')
			self._crear_nodo(
				identificacion, self._cbc, 'ID',
				texto=(movimiento.product_id.default_code or '-')[:30]
			)
			numero += 1
		return numero - 1

	def _obtener_lineas_despacho_grt(self, stock_id):
		"""Decide entre la línea de anotación (ID 0) y el detalle de bienes.

		Casos intermedios (09 electrónica, 01/04 electrónicos + total,
		50/52 + total): la línea 0 sería ERROR 3458 y el detalle solo una
		OBSERVACIÓN 4434, así que se emite el detalle."""
		if self._admite_linea_anotacion(stock_id):
			self._obtener_linea_anotacion_grt(stock_id)
			return
		if not self._obtener_lineas_bienes_grt(stock_id):
			# El XSD exige al menos una línea; sin movimientos con cantidad
			# se emite la anotación (SUNAT responderá 3435/3458).
			self._obtener_linea_anotacion_grt(stock_id)

	# ------------------------------------------------------------------
	# Documento completo
	# ------------------------------------------------------------------
	def getGuide(self, stock_id, data):
		xmlns = etree.QName(
			"urn:oasis:names:specification:ubl:schema:xsd:DespatchAdvice-2",
			'DespatchAdvice'
		)
		nsmap1 = OrderedDict([
			(None, xmlns.namespace), ('cac', self._cac), ('cbc', self._cbc),
			('ccts', self._ccts), ('ds', self._ds), ('ext', self._ext),
			('qdt', self._qdt), ('sac', self._sac), ('udt', self._udt),
			('xsi', self._xsi),
		])
		self._root = etree.Element(xmlns.text, nsmap=nsmap1)

		# --- Extensión de firma -----------------------------------------
		extensiones = self._crear_nodo(self._root, self._ext, 'UBLExtensions')
		extension = self._crear_nodo(extensiones, self._ext, 'UBLExtension')
		contenido = self._crear_nodo(extension, self._ext, 'ExtensionContent')
		self._getX509Template(contenido)

		# --- Cabecera (campos 1 a 7) ------------------------------------
		self._getUBLVersion()
		self._crear_nodo(
			self._root, self._cbc, 'ID', texto=stock_id.pe_guide_number or ''
		)
		self._crear_nodo(
			self._root, self._cbc, 'IssueDate', texto=str(stock_id.pe_date_issue)
		)
		fecha_peru = convertir_fecha_a_peru(
			stock_id.date_done or stock_id.scheduled_date
		)
		self._crear_nodo(
			self._root, self._cbc, 'IssueTime',
			texto=fecha_peru.strftime("%H:%M:%S") if fecha_peru else '00:00:00'
		)
		self._crear_nodo(
			self._root, self._cbc, 'DespatchAdviceTypeCode', texto='31'
		)
		if stock_id.note:
			self._crear_nodo(
				self._root, self._cbc, 'Note', texto=str(stock_id.note)[:250]
			)

		# --- Documentos relacionados (campos 12 a 15) --------------------
		# Reutiliza el generador del módulo base: One2many + IssuerParty
		# con RUC del emisor (SUNAT 01/06/2026).
		self._obtener_documentos_relacionados(stock_id)

		# --- Firma y partes ---------------------------------------------
		self._getSignature(stock_id)
		# En la GRT el cac:DespatchSupplierParty es el TRANSPORTISTA, es
		# decir la propia compañía emisora (campos 8 y 9).
		self._getCompany(stock_id)
		self._obtener_destinatario(stock_id)
		self._obtener_pagador_flete(stock_id)

		# --- Shipment ----------------------------------------------------
		shipment = self._crear_nodo(self._root, self._cac, 'Shipment')
		# Identificador de traslado de valor fijo (campo 49).
		self._crear_nodo(shipment, self._cbc, 'ID', texto='SUNAT_Envio')
		self._crear_nodo(
			shipment, self._cbc, 'GrossWeightMeasure',
			texto=str(stock_id.pe_gross_weight),
			unitCode=stock_id.pe_grt_peso_unidad or 'KGM'
		)
		self._obtener_indicadores_grt(shipment, stock_id)
		self._obtener_subcontratador(shipment, stock_id)

		# --- ShipmentStage ----------------------------------------------
		stage = self._crear_nodo(shipment, self._cac, 'ShipmentStage')
		periodo = self._crear_nodo(stage, self._cac, 'TransitPeriod')
		fecha_inicio = stock_id.pe_grt_fecha_inicio_traslado or stock_id.pe_date_issue
		self._crear_nodo(
			periodo, self._cbc, 'StartDate',
			texto=fecha_inicio.strftime('%Y-%m-%d')
		)
		self._obtener_transportista_stage(stage, stock_id)

		# Tipo de evento (campo 59) - uso exclusivo de transbordo no
		# programado / imposibilidad de arribo o entrega.
		if stock_id.pe_grt_tipo_evento:
			evento = self._crear_nodo(stage, self._cac, 'TransportEvent')
			self._crear_nodo(
				evento, self._cbc, 'TransportEventTypeCode',
				texto=stock_id.pe_grt_tipo_evento
			)

		self._obtener_conductores(stage, stock_id)

		# --- Delivery y vehículos ---------------------------------------
		self._obtener_puntos_traslado(shipment, stock_id)
		self._obtener_vehiculos(shipment, stock_id)

		# --- Líneas: detalle de bienes o anotación (ID 0) --------------
		self._obtener_lineas_despacho_grt(stock_id)

		return etree.tostring(
			self._root, pretty_print=True, xml_declaration=True,
			encoding='utf-8', standalone=False
		)

	def getGuideVoided(self, data):
		"""Comunicación de baja de la GRT."""
		xmlns = etree.QName(
			"urn:oasis:names:specification:ubl:schema:xsd:DespatchAdvice-2",
			'DespatchAdvice'
		)
		nsmap1 = OrderedDict([
			(None, xmlns.namespace), ('cac', self._cac), ('cbc', self._cbc),
			('ccts', self._ccts), ('ds', self._ds), ('ext', self._ext),
			('qdt', self._qdt), ('sac', self._sac), ('udt', self._udt),
			('xsi', self._xsi),
		])
		self._root = etree.Element(xmlns.text, nsmap=nsmap1)

		extensiones = self._crear_nodo(self._root, self._ext, 'UBLExtensions')
		extension = self._crear_nodo(extensiones, self._ext, 'UBLExtension')
		contenido = self._crear_nodo(extension, self._ext, 'ExtensionContent')
		self._getX509Template(contenido)

		self._getUBLVersion()
		self._crear_nodo(self._root, self._cbc, 'ID', texto=data.name)
		self._crear_nodo(self._root, self._cbc, 'IssueDate', texto=str(data.date))
		self._crear_nodo(
			self._root, self._cbc, 'DespatchAdviceTypeCode', texto='31'
		)

		for linea in data.voided_ids:
			referencia = self._crear_nodo(self._root, self._cac, 'OrderReference')
			self._crear_nodo(
				referencia, self._cbc, 'ID', texto=linea.pe_guide_number
			)
			self._crear_nodo(
				referencia, self._cbc, 'OrderTypeCode', texto='31',
				name=u"GUIA DE REMISIÓN TRANSPORTISTA"
			)

		self._getSignature(data)
		self._getCompany(data)

		return etree.tostring(
			self._root, pretty_print=True, xml_declaration=True,
			encoding='utf-8', standalone=False
		)


def get_document_transport(registro):
	"""Punto de entrada usado por solse.cpe.eguide.transport."""
	if registro.type == "sync":
		return EGuideTransport().getGuide(registro.picking_ids[0], registro)
	return EGuideTransport().getGuideVoided(registro)
