# -*- coding: utf-8 -*-

#
# Reglas de validación SUNAT publicadas al 20/06/2026, hoja Guía-Remitente2_0,
# campos 46 al 55. Caso: modalidad 01-Público en el que el remitente consigna
# los vehículos y conductores del transportista (último párrafo del numeral
# 3.1 del artículo 3 de la RS 255-2015/SUNAT).

from datetime import date

from lxml import etree
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.solse_pe_cpe_guias.models.eguide import EGuide

from .common import TestGuiaCommon

NS_CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
NS_CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"


@tagged('post_install', '-at_install', 'solse_pe_cpe_guias')
class TestVehiculosConductores(TestGuiaCommon):

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.FleetLineObj = cls.env['pe.stock.fleet'].sudo()
		cls.VehicleObj = cls.env['fleet.vehicle'].sudo()

		cls.partner_transportista = cls._crear_partner_ruc(
			'Transportes Test SAC', '20500000005'
		)
		cls.partner_transportista.pe_mtc_number = 'MTC0001234'

		cls.conductor = cls.PartnerObj.create({
			'name': 'Juan Perez Lopez',
			'company_type': 'person',
			'vat': '44556677',
			'pe_driver_license': 'Q44556677',
			'l10n_latam_identification_type_id': cls.tipo_dni
				and cls.tipo_dni.id or False,
		})
		cls.conductor_2 = cls.PartnerObj.create({
			'name': 'Pedro Ramos Diaz',
			'company_type': 'person',
			'vat': '11223344',
			'pe_driver_license': 'Q11223344',
			'l10n_latam_identification_type_id': cls.tipo_dni
				and cls.tipo_dni.id or False,
		})

	# ------------------------------------------------------------------
	# Helpers
	# ------------------------------------------------------------------

	def _crear_picking_publico_con_registro(self, **overrides):
		vals = {
			'pe_transport_mode': '01',
			'pe_carrier_id': self.partner_transportista.id,
			'pe_registro_vehiculos_conductores': True,
			'pe_delivery_date': date.today(),
		}
		vals.update(overrides)
		return self._crear_picking(**vals)

	def _agregar_vehiculo(self, picking, placa='ABC123', conductor=None,
						  principal=True, tuce='15M22019162E'):
		return self.FleetLineObj.create({
			'picking_id': picking.id,
			'name': placa,
			'driver_id': (conductor or self.conductor).id,
			'is_main': principal,
			'pe_tuce': tuce,
		})

	def _generar_unidades_manejo(self, picking):
		"""Genera el bloque cac:TransportHandlingUnit de un picking."""
		eguide = EGuide()
		shipment = etree.Element(f"{{{NS_CAC}}}Shipment", nsmap={'cac': NS_CAC})
		eguide._obtener_unidades_manejo(shipment, picking)
		return shipment

	# ------------------------------------------------------------------
	# Helper de decisión
	# ------------------------------------------------------------------

	def test_emite_en_modalidad_02(self):
		picking = self._crear_picking(pe_transport_mode='02')
		self.assertTrue(picking._emite_vehiculos_conductores())

	def test_no_emite_en_modalidad_01_sin_indicador(self):
		picking = self._crear_picking(
			pe_transport_mode='01',
			pe_carrier_id=self.partner_transportista.id,
		)
		self.assertFalse(picking._emite_vehiculos_conductores())

	def test_emite_en_modalidad_01_con_indicador(self):
		picking = self._crear_picking(
			pe_transport_mode='01',
			pe_carrier_id=self.partner_transportista.id,
			pe_registro_vehiculos_conductores=True,
		)
		self.assertTrue(picking._emite_vehiculos_conductores())

	def test_no_emite_con_m1_l(self):
		"""ERR-3455: en traslados M1/L nunca se consigna conductor."""
		picking = self._crear_picking(
			pe_transport_mode='01',
			pe_carrier_id=self.partner_transportista.id,
			pe_registro_vehiculos_conductores=True,
			pe_vehiculos_m1_l=True,
		)
		self.assertFalse(picking._emite_vehiculos_conductores())

	# ------------------------------------------------------------------
	# Validaciones cliente-side
	# ------------------------------------------------------------------

	def test_err_3354_vehiculo_prohibido_sin_indicador(self):
		"""Modalidad 01 sin indicador no admite placa ni conductor."""
		picking = self._crear_picking(
			pe_transport_mode='01',
			pe_carrier_id=self.partner_transportista.id,
		)
		self._agregar_vehiculo(picking)
		with self.assertRaises(UserError):
			picking._validar_vehiculos_conductores()

	def test_err_3358_un_solo_principal(self):
		picking = self._crear_picking(pe_transport_mode='02')
		self._agregar_vehiculo(picking, placa='ABC123', principal=True)
		self._agregar_vehiculo(picking, placa='DEF456',
							   conductor=self.conductor_2, principal=True)
		with self.assertRaises(UserError):
			picking._validar_vehiculos_conductores()

	def test_err_2567_formato_placa(self):
		picking = self._crear_picking(pe_transport_mode='02')
		self._agregar_vehiculo(picking, placa='AB-123')
		with self.assertRaises(UserError):
			picking._validar_vehiculos_conductores()

	def test_err_3355_formato_tuce(self):
		picking = self._crear_picking(pe_transport_mode='02')
		self._agregar_vehiculo(picking, tuce='CORTA123')
		with self.assertRaises(UserError):
			picking._validar_vehiculos_conductores()

	def test_err_2572_licencia_obligatoria(self):
		conductor_sin_licencia = self.PartnerObj.create({
			'name': 'Sin Licencia Test',
			'company_type': 'person',
		})
		picking = self._crear_picking(pe_transport_mode='02')
		self._agregar_vehiculo(picking, conductor=conductor_sin_licencia)
		with self.assertRaises(UserError):
			picking._validar_vehiculos_conductores()

	def test_err_3451_indicadores_excluyentes(self):
		"""ERR-3451: registro de vehículos + M1/L no pueden coexistir."""
		picking = self._crear_picking(
			pe_transport_mode='01',
			pe_carrier_id=self.partner_transportista.id,
			pe_registro_vehiculos_conductores=True,
			pe_vehiculos_m1_l=True,
		)
		with self.assertRaises(UserError):
			picking._validar_indicadores_y_contenedores()

	# ------------------------------------------------------------------
	# OBS-4399 configurable por parámetro del sistema
	# ------------------------------------------------------------------

	def _fijar_parametro_tuce(self, valor):
		self.env['ir.config_parameter'].sudo().set_param(
			'solse_pe_cpe_guias.tuce_obligatoria', valor
		)

	def test_obs_4399_no_bloquea_por_defecto(self):
		"""Sin TUCE y con el parámetro en 0, la guía debe poder emitirse."""
		self._fijar_parametro_tuce('0')
		picking = self._crear_picking_publico_con_registro()
		self._agregar_vehiculo(picking, tuce=False)
		# No debe levantar excepción.
		picking._validar_vehiculos_conductores()

	def test_obs_4399_bloquea_con_parametro_activo(self):
		self._fijar_parametro_tuce('1')
		picking = self._crear_picking_publico_con_registro()
		self._agregar_vehiculo(picking, tuce=False)
		with self.assertRaises(UserError):
			picking._validar_vehiculos_conductores()

	def test_obs_es_bloqueante_tolera_parametro_vacio(self):
		"""Si el parámetro se borra o queda vacío, no debe trabar el sistema."""
		self._fijar_parametro_tuce('')
		picking = self._crear_picking(pe_transport_mode='02')
		self.assertFalse(picking._obs_es_bloqueante(
			'solse_pe_cpe_guias.tuce_obligatoria'
		))
		self.assertFalse(picking._obs_es_bloqueante('clave.inexistente.xyz'))

	def test_obs_es_bloqueante_acepta_sinonimos(self):
		picking = self._crear_picking(pe_transport_mode='02')
		for valor in ('1', 'true', 'TRUE', ' Si ', 'sí', 'x', 'on'):
			self._fijar_parametro_tuce(valor)
			self.assertTrue(
				picking._obs_es_bloqueante(
					'solse_pe_cpe_guias.tuce_obligatoria'),
				"El valor %r debería interpretarse como verdadero" % valor
			)
		for valor in ('0', 'false', 'no', 'cualquier cosa'):
			self._fijar_parametro_tuce(valor)
			self.assertFalse(
				picking._obs_es_bloqueante(
					'solse_pe_cpe_guias.tuce_obligatoria'),
				"El valor %r debería interpretarse como falso" % valor
			)

	# ------------------------------------------------------------------
	# Generación XML
	# ------------------------------------------------------------------

	def test_xml_driver_person_en_modalidad_01_con_indicador(self):
		"""ERR-3357: el conductor principal debe salir en el XML."""
		picking = self._crear_picking(
			pe_transport_mode='01',
			pe_carrier_id=self.partner_transportista.id,
			pe_registro_vehiculos_conductores=True,
		)
		self._agregar_vehiculo(picking)
		self.assertTrue(picking._emite_vehiculos_conductores())

	def test_xml_tuce_en_transport_equipment(self):
		"""OBS-4399: la TUCE va en ApplicableTransportMeans."""
		picking = self._crear_picking(
			pe_transport_mode='01',
			pe_carrier_id=self.partner_transportista.id,
			pe_registro_vehiculos_conductores=True,
		)
		self._agregar_vehiculo(picking)
		shipment = self._generar_unidades_manejo(picking)

		tuces = shipment.findall(
			f'.//{{{NS_CAC}}}ApplicableTransportMeans/'
			f'{{{NS_CBC}}}RegistrationNationalityID'
		)
		self.assertEqual(len(tuces), 1)
		self.assertEqual(tuces[0].text, '15M22019162E')

	def test_xml_tuce_suprimida_sin_indicador(self):
		"""ERR-3452: sin el indicador la TUCE no debe emitirse."""
		picking = self._crear_picking(
			pe_transport_mode='01',
			pe_carrier_id=self.partner_transportista.id,
		)
		self._agregar_vehiculo(picking)
		shipment = self._generar_unidades_manejo(picking)

		tuces = shipment.findall(
			f'.//{{{NS_CAC}}}ApplicableTransportMeans/'
			f'{{{NS_CBC}}}RegistrationNationalityID'
		)
		self.assertEqual(len(tuces), 0)
