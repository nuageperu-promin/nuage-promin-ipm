# -*- coding: utf-8 -*-

from lxml import etree
from odoo.tests import tagged

from odoo.addons.solse_pe_cpe_guias.models.eguide import EGuide

from .common import TestGuiaCommon


NS_CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
NS_CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"


@tagged('post_install', '-at_install', 'solse_pe_cpe_guias')
class TestXmlDocumentosRelacionados(TestGuiaCommon):
	"""Tests de generación XML para AdditionalDocumentReference + IssuerParty."""

	def _generar_root_con_docs(self, picking):
		"""Helper: crea un EGuide con root vacío, invoca el método auxiliar
		y devuelve el root."""
		eguide = EGuide()
		eguide._root = etree.Element('Root')
		eguide._obtener_documentos_relacionados(picking)
		return eguide._root

	def test_doc_tipo_01_genera_issuer_party(self):
		"""Doc tipo 01-Factura debe generar cac:IssuerParty con RUC."""
		picking = self._crear_picking(pe_transfer_code='02')
		self.DocRelObj.create({
			'picking_id': picking.id,
			'codigo_documento': '01',
			'numero_documento': 'F001-1',
			'emisor_id': self.partner_emisor_doc.id,
		})
		root = self._generar_root_con_docs(picking)

		referencias = root.findall(f'{{{NS_CAC}}}AdditionalDocumentReference')
		self.assertEqual(len(referencias), 1)

		issuer = referencias[0].find(f'{{{NS_CAC}}}IssuerParty')
		self.assertIsNotNone(issuer, "Tipo 01 debe generar IssuerParty")

		party_id = issuer.find(
			f'{{{NS_CAC}}}PartyIdentification/{{{NS_CBC}}}ID'
		)
		self.assertEqual(party_id.text, self.partner_emisor_doc.doc_number)

	def test_doc_tipo_50_no_genera_issuer_party(self):
		"""Doc tipo 50-DAM NO debe generar IssuerParty (no está en la lista)."""
		picking = self._crear_picking(pe_transfer_code='09')
		self.DocRelObj.create({
			'picking_id': picking.id,
			'codigo_documento': '50',
			'numero_documento': '118-2026-10-123456',
		})
		root = self._generar_root_con_docs(picking)
		referencia = root.find(f'{{{NS_CAC}}}AdditionalDocumentReference')
		self.assertIsNone(
			referencia.find(f'{{{NS_CAC}}}IssuerParty'),
			"Tipo 50 NO debe tener IssuerParty"
		)

	def test_multiples_documentos_generan_multiples_referencias(self):
		"""N documentos en One2many generan N AdditionalDocumentReference."""
		picking = self._crear_picking(pe_transfer_code='09')
		self.DocRelObj.create({
			'picking_id': picking.id,
			'codigo_documento': '50',
			'numero_documento': '118-2026-10-111111',
		})
		self.DocRelObj.create({
			'picking_id': picking.id,
			'codigo_documento': '49',
			'numero_documento': '000000001',
		})
		root = self._generar_root_con_docs(picking)
		referencias = root.findall(f'{{{NS_CAC}}}AdditionalDocumentReference')
		self.assertEqual(len(referencias), 2)

	def test_documento_type_code_anidado_correctamente(self):
		"""Anti-regresión del bug v1: cbc:DocumentTypeCode debe estar
		dentro de cac:AdditionalDocumentReference, no en el root."""
		picking = self._crear_picking(pe_transfer_code='09')
		self.DocRelObj.create({
			'picking_id': picking.id,
			'codigo_documento': '50',
			'numero_documento': '118-2026-10-123456',
		})
		root = self._generar_root_con_docs(picking)

		# DocumentTypeCode NO debe estar como hijo directo del root
		hijos_directos = root.findall(f'{{{NS_CBC}}}DocumentTypeCode')
		self.assertEqual(len(hijos_directos), 0)

		# DEBE estar dentro de AdditionalDocumentReference
		referencia = root.find(f'{{{NS_CAC}}}AdditionalDocumentReference')
		tipo_code = referencia.find(f'{{{NS_CBC}}}DocumentTypeCode')
		self.assertIsNotNone(tipo_code)
		self.assertEqual(tipo_code.text, '50')


@tagged('post_install', '-at_install', 'solse_pe_cpe_guias')
class TestXmlContenedores(TestGuiaCommon):
	"""Tests de generación XML para TransportHandlingUnit + TransportEquipment."""

	def _generar_shipment_con_contenedores(self, picking):
		eguide = EGuide()
		shipment = etree.Element(f"{{{NS_CAC}}}Shipment", nsmap={'cac': NS_CAC})
		eguide._obtener_unidades_manejo(shipment, picking)
		return shipment

	def test_sin_contenedores_no_genera_handling_unit(self):
		"""Picking sin contenedores no debe generar TransportHandlingUnit."""
		picking = self._crear_picking()
		shipment = self._generar_shipment_con_contenedores(picking)
		self.assertEqual(
			len(shipment.findall(f'{{{NS_CAC}}}TransportHandlingUnit')), 0
		)

	def test_un_contenedor_genera_estructura_completa(self):
		"""Un contenedor con precinto genera ID y TraceID."""
		picking = self._crear_picking()
		self.ContObj.create({
			'picking_id': picking.id,
			'numero_contenedor': 'TCKU1234567',
			'numero_precinto': 'PRECINTO-001',
		})
		shipment = self._generar_shipment_con_contenedores(picking)
		equipment = shipment.find(
			f'{{{NS_CAC}}}TransportHandlingUnit/{{{NS_CAC}}}TransportEquipment'
		)
		self.assertIsNotNone(equipment)
		self.assertEqual(
			equipment.find(f'{{{NS_CBC}}}ID').text, 'TCKU1234567'
		)
		self.assertEqual(
			equipment.find(f'{{{NS_CBC}}}TraceID').text, 'PRECINTO-001'
		)

	def test_contenedor_sin_precinto_omite_trace_id(self):
		"""Contenedor sin precinto NO debe generar TraceID vacío."""
		picking = self._crear_picking()
		self.ContObj.create({
			'picking_id': picking.id,
			'numero_contenedor': 'TCKU1234567',
		})
		shipment = self._generar_shipment_con_contenedores(picking)
		equipment = shipment.find(
			f'{{{NS_CAC}}}TransportHandlingUnit/{{{NS_CAC}}}TransportEquipment'
		)
		self.assertIsNone(equipment.find(f'{{{NS_CBC}}}TraceID'))

	def test_multiples_contenedores_generan_multiples_handling_units(self):
		"""N contenedores generan N TransportHandlingUnit."""
		picking = self._crear_picking()
		self.ContObj.create({
			'picking_id': picking.id,
			'numero_contenedor': 'TCKU1111111',
		})
		self.ContObj.create({
			'picking_id': picking.id,
			'numero_contenedor': 'MSCU2222222',
		})
		shipment = self._generar_shipment_con_contenedores(picking)
		self.assertEqual(
			len(shipment.findall(f'{{{NS_CAC}}}TransportHandlingUnit')), 2
		)

	def test_subregimen_19_92_suprime_handling_units(self):
		"""Sub-régimen 19+92 suprime contenedores aunque existan."""
		picking = self._crear_picking(pe_transfer_code='19')
		self.DocRelObj.create({
			'picking_id': picking.id,
			'codigo_documento': '92',
			'numero_documento': 'CITA-001',
			'emisor_id': self.partner_terminal_portuario.id,
		})
		# Forzamos contenedor via SQL para no caer en la validación cliente
		self.env.cr.execute("""
			INSERT INTO pe_stock_contenedor
			(picking_id, numero_contenedor, sequence)
			VALUES (%s, 'TCKU1234567', 10)
		""", (picking.id,))
		picking.invalidate_recordset()
		self.assertTrue(picking.pe_es_subregimen_19_92)

		shipment = self._generar_shipment_con_contenedores(picking)
		self.assertEqual(
			len(shipment.findall(f'{{{NS_CAC}}}TransportHandlingUnit')), 0
		)


@tagged('post_install', '-at_install', 'solse_pe_cpe_guias')
class TestXmlSubregimen1992(TestGuiaCommon):
	"""Tests de la DespatchLine dummy en sub-régimen 19+92."""

	def test_linea_dummy_generada_en_subregimen(self):
		"""En sub-régimen se genera UNA línea con descripción genérica."""
		picking = self._crear_picking(pe_transfer_code='19')
		self.DocRelObj.create({
			'picking_id': picking.id,
			'codigo_documento': '92',
			'numero_documento': 'CITA-001',
			'emisor_id': self.partner_terminal_portuario.id,
		})
		picking.invalidate_recordset()

		eguide = EGuide()
		eguide._root = etree.Element('Root')
		eguide._obtener_lineas_despacho(picking)

		lineas = eguide._root.findall(f'{{{NS_CAC}}}DespatchLine')
		self.assertEqual(
			len(lineas), 1,
			"Sub-régimen 19+92 debe generar UNA SOLA línea dummy"
		)

		# La descripción debe ser la genérica del sub-régimen
		descripcion = lineas[0].find(
			f'{{{NS_CAC}}}Item/{{{NS_CBC}}}Description'
		)
		self.assertEqual(descripcion.text, 'TRASLADO DE MERCANCIA EXTRANJERA')

		# La cantidad debe ser 1 NIU
		cantidad = lineas[0].find(f'{{{NS_CBC}}}DeliveredQuantity')
		self.assertEqual(cantidad.text, '1')
		self.assertEqual(cantidad.get('unitCode'), 'NIU')
