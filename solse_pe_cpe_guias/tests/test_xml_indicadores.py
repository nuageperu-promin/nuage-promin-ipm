# -*- coding: utf-8 -*-

#
# IMPORTANTE: estos tests son la red de seguridad contra el INFO-3388 SUNAT.
# Si SUNAT cambia los nombres de indicadores en futuras publicaciones,
# estos tests fallarán y obligarán a actualizar el código.

from lxml import etree
from odoo.tests import tagged

from odoo.addons.solse_pe_cpe_guias.models.eguide import EGuide

from .common import TestGuiaCommon


# Lista oficial SUNAT de valores aceptados en cbc:SpecialInstructions.
# Fuente: hoja Guía-Remitente2_0 del Excel de Reglas de Validación SUNAT
# publicado al 01/06/2026 - validación INFO-3388.
INDICADORES_OFICIALES_SUNAT = {
	'SUNAT_Envio_IndicadorTransbordoProgramado',
	'SUNAT_Envio_IndicadorTrasladoVehiculoM1L',
	'SUNAT_Envio_IndicadorRetornoVehiculoVacio',
	'SUNAT_Envio_IndicadorRetornoVehiculoEnvaseVacio',
	'SUNAT_Envio_IndicadorVehiculoConductoresTransp',
	'SUNAT_Envio_IndicadorTrasladoTotalDAMoDS',
	'SUNAT_Envio_IndicadorTrasladoContenedorManifiestoCarga',
}

NS_CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
NS_CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"


@tagged('post_install', '-at_install', 'solse_pe_cpe_guias')
class TestXmlIndicadores(TestGuiaCommon):
	"""Tests de generación XML del bloque SpecialInstructions.
	Protege contra el INFO-3388 (nombres de indicadores incorrectos).
	"""

	def _generar_shipment_con_indicadores(self, picking):
		"""Helper: instancia EGuide, crea un shipment vacío e invoca
		el método auxiliar de indicadores. Devuelve el element shipment."""
		eguide = EGuide()
		shipment = etree.Element(f"{{{NS_CAC}}}Shipment", nsmap={'cac': NS_CAC})
		eguide._obtener_instrucciones_especiales(shipment, picking)
		return shipment

	def _extraer_indicadores(self, shipment):
		"""Devuelve la lista de valores de cbc:SpecialInstructions."""
		return [
			el.text for el in shipment.findall(f'{{{NS_CBC}}}SpecialInstructions')
		]

	# ------------------------------------------------------------------
	# Test crítico: los 7 nombres deben coincidir EXACTAMENTE con SUNAT
	# ------------------------------------------------------------------

	def test_todos_indicadores_son_nombres_oficiales_sunat(self):
		"""Activa los 7 indicadores y verifica que cada nombre generado
		esté en la lista oficial SUNAT (anti-bug INFO-3388)."""
		picking = self._crear_picking(
			pe_transport_mode='01',
			pe_traslado_total_dam=True,
			pe_traslado_contenedor_mc=True,
			pe_transbordo_programado=True,
			pe_registro_vehiculos_conductores=False,
			# transbordo y registro son excluyentes; lo testeo aparte abajo
			pe_vehiculos_m1_l=True,
			pe_retorno_vehiculo_vacio=True,
			pe_retorno_envase_vacio=True,
		)
		shipment = self._generar_shipment_con_indicadores(picking)
		generados = self._extraer_indicadores(shipment)

		# Cada indicador generado debe ser un nombre oficial SUNAT
		for valor in generados:
			self.assertIn(
				valor, INDICADORES_OFICIALES_SUNAT,
				f"Indicador '{valor}' no está en la lista oficial SUNAT "
				f"(INFO-3388). Si SUNAT cambió los nombres, actualizar "
				f"INDICADORES_OFICIALES_SUNAT en este test."
			)

	def test_traslado_total_genera_nombre_exacto(self):
		"""IndicadorTrasladoTotalDAMoDS - nombre exacto."""
		picking = self._crear_picking(pe_traslado_total_dam=True)
		shipment = self._generar_shipment_con_indicadores(picking)
		self.assertIn(
			'SUNAT_Envio_IndicadorTrasladoTotalDAMoDS',
			self._extraer_indicadores(shipment)
		)

	def test_contenedor_mc_genera_nombre_exacto(self):
		"""IndicadorTrasladoContenedorManifiestoCarga - nombre exacto.
		NO debe ser IndicadorTrasladoEnContenedorMC (nombre incorrecto
		del bug del 03/06/2026)."""
		picking = self._crear_picking(pe_traslado_contenedor_mc=True)
		shipment = self._generar_shipment_con_indicadores(picking)
		indicadores = self._extraer_indicadores(shipment)
		self.assertIn(
			'SUNAT_Envio_IndicadorTrasladoContenedorManifiestoCarga',
			indicadores
		)
		# Anti-regresión explícita
		self.assertNotIn(
			'SUNAT_Envio_IndicadorTrasladoEnContenedorMC', indicadores
		)

	def test_transbordo_programado_genera_nombre_exacto(self):
		"""IndicadorTransbordoProgramado - nombre exacto."""
		picking = self._crear_picking(
			pe_transport_mode='01',
			pe_transbordo_programado=True,
		)
		shipment = self._generar_shipment_con_indicadores(picking)
		self.assertIn(
			'SUNAT_Envio_IndicadorTransbordoProgramado',
			self._extraer_indicadores(shipment)
		)

	def test_registro_vehiculos_genera_nombre_exacto(self):
		"""IndicadorVehiculoConductoresTransp - nombre exacto.
		NO debe ser IndicadorRegistroVehiculosConductoresTransp (nombre
		incorrecto del bug del 03/06/2026)."""
		picking = self._crear_picking(
			pe_transport_mode='01',
			pe_registro_vehiculos_conductores=True,
		)
		shipment = self._generar_shipment_con_indicadores(picking)
		indicadores = self._extraer_indicadores(shipment)
		self.assertIn(
			'SUNAT_Envio_IndicadorVehiculoConductoresTransp', indicadores
		)
		# Anti-regresión explícita
		self.assertNotIn(
			'SUNAT_Envio_IndicadorRegistroVehiculosConductoresTransp',
			indicadores
		)

	def test_vehiculos_m1_l_genera_nombre_exacto(self):
		"""IndicadorTrasladoVehiculoM1L - nombre exacto.
		NO debe ser IndicadorTrasladoVehiculosCategoriaM1L (nombre
		incorrecto del bug del 03/06/2026)."""
		picking = self._crear_picking(pe_vehiculos_m1_l=True)
		shipment = self._generar_shipment_con_indicadores(picking)
		indicadores = self._extraer_indicadores(shipment)
		self.assertIn(
			'SUNAT_Envio_IndicadorTrasladoVehiculoM1L', indicadores
		)
		# Anti-regresión explícita
		self.assertNotIn(
			'SUNAT_Envio_IndicadorTrasladoVehiculosCategoriaM1L', indicadores
		)

	def test_retorno_vehiculo_vacio_genera_nombre_exacto(self):
		"""IndicadorRetornoVehiculoVacio - nombre exacto."""
		picking = self._crear_picking(pe_retorno_vehiculo_vacio=True)
		shipment = self._generar_shipment_con_indicadores(picking)
		self.assertIn(
			'SUNAT_Envio_IndicadorRetornoVehiculoVacio',
			self._extraer_indicadores(shipment)
		)

	def test_retorno_envase_vacio_genera_nombre_exacto(self):
		"""IndicadorRetornoVehiculoEnvaseVacio - nombre exacto."""
		picking = self._crear_picking(pe_retorno_envase_vacio=True)
		shipment = self._generar_shipment_con_indicadores(picking)
		self.assertIn(
			'SUNAT_Envio_IndicadorRetornoVehiculoEnvaseVacio',
			self._extraer_indicadores(shipment)
		)

	# ------------------------------------------------------------------
	# Comportamiento esperado del método
	# ------------------------------------------------------------------

	def test_sin_indicadores_no_genera_special_instructions(self):
		"""Picking sin indicadores activos no debe generar el tag."""
		picking = self._crear_picking()
		shipment = self._generar_shipment_con_indicadores(picking)
		self.assertEqual(self._extraer_indicadores(shipment), [])

	def test_subregimen_19_92_suprime_indicadores(self):
		"""En sub-régimen 19+92 no se emiten SpecialInstructions
		aunque los indicadores estén activos en el picking."""
		picking = self._crear_picking(
			pe_transfer_code='19',
			pe_traslado_total_dam=True,
			pe_vehiculos_m1_l=True,
		)
		self.DocRelObj.create({
			'picking_id': picking.id,
			'codigo_documento': '92',
			'numero_documento': 'CITA-001',
			'emisor_id': self.partner_terminal_portuario.id,
		})
		picking.invalidate_recordset()
		self.assertTrue(picking.pe_es_subregimen_19_92)

		shipment = self._generar_shipment_con_indicadores(picking)
		self.assertEqual(
			self._extraer_indicadores(shipment), [],
			"Sub-régimen 19+92 debe suprimir TODOS los SpecialInstructions"
		)
