# -*- coding: utf-8 -*-

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import TestGuiaCommon


@tagged('post_install', '-at_install', 'solse_pe_cpe_guias')
class TestIndicadoresContenedores(TestGuiaCommon):
	"""Tests para validaciones SUNAT 01/06/2026 de indicadores y contenedores.
	Cubre: ERR-3615, ERR-3485, ERR-3419, ERR-3420, ERR-3421, ERR-3422,
	ERR-3621, ERR-3631, ERR-3632 y el relleno de bultos de validate_eguide().
	"""

	# ------------------------------------------------------------------
	# ERR-3615 - Exclusión transbordo programado vs registro vehículos
	# ------------------------------------------------------------------

	def test_err_3615_transbordo_y_registro_juntos_falla(self):
		"""Modalidad 01: transbordo programado + registro vehículos = error."""
		picking = self._crear_picking(
			pe_transport_mode='01',
			pe_transbordo_programado=True,
			pe_registro_vehiculos_conductores=True,
		)
		with self.assertRaisesRegex(
			UserError, 'simultáneamente.*Transbordo.*Registro'
		):
			picking._validar_indicadores_y_contenedores()

	def test_err_3615_solo_transbordo_pasa(self):
		"""Modalidad 01 con solo transbordo programado (sin registro) ok."""
		picking = self._crear_picking(
			pe_transport_mode='01',
			pe_transbordo_programado=True,
			pe_registro_vehiculos_conductores=False,
		)
		# No debe levantar
		picking._validar_indicadores_y_contenedores()

	def test_err_3615_solo_registro_pasa(self):
		"""Modalidad 01 con solo registro vehículos ok."""
		picking = self._crear_picking(
			pe_transport_mode='01',
			pe_transbordo_programado=False,
			pe_registro_vehiculos_conductores=True,
		)
		picking._validar_indicadores_y_contenedores()

	def test_transbordo_solo_aplica_modalidad_01(self):
		"""pe_transbordo_programado en modalidad 02 debe fallar."""
		picking = self._crear_picking(
			pe_transport_mode='02',
			pe_transbordo_programado=True,
		)
		with self.assertRaisesRegex(UserError, "Transbordo programado.*modalidad"):
			picking._validar_indicadores_y_contenedores()

	def test_registro_vehiculos_solo_aplica_modalidad_01(self):
		"""pe_registro_vehiculos_conductores en modalidad 02 debe fallar."""
		picking = self._crear_picking(
			pe_transport_mode='02',
			pe_registro_vehiculos_conductores=True,
		)
		with self.assertRaisesRegex(UserError, "Registro de vehículos.*modalidad"):
			picking._validar_indicadores_y_contenedores()

	# ------------------------------------------------------------------
	# ERR-3485 - Traslado total DAM/DS solo aplica a docs 50 o 52
	# ------------------------------------------------------------------

	def test_err_3485_traslado_total_sin_doc_50_52_falla(self):
		"""Activar pe_traslado_total_dam sin doc 50/52 debe fallar."""
		picking = self._crear_picking(
			pe_transfer_code='08',
			pe_traslado_total_dam=True,
		)
		# Sin documentos relacionados
		with self.assertRaisesRegex(UserError, 'requiere.*50.*DAM.*52.*DS'):
			picking._validar_indicadores_y_contenedores()

	def test_err_3485_traslado_total_con_motivo_13_falla(self):
		"""pe_traslado_total_dam con motivo distinto a 08/19 debe fallar."""
		picking = self._crear_picking(
			pe_transfer_code='13',
			pe_traslado_total_dam=True,
		)
		self.DocRelObj.create({
			'picking_id': picking.id,
			'codigo_documento': '50',
			'numero_documento': '118-2026-10-123456',
		})
		with self.assertRaisesRegex(UserError, 'solo aplica.*motivos.*08.*19'):
			picking._validar_indicadores_y_contenedores()

	def test_traslado_total_con_motivo_08_y_dam_pasa(self):
		"""Combinación válida: motivo 08 + doc 50 + traslado total."""
		picking = self._crear_picking(
			pe_transfer_code='08',
			pe_traslado_total_dam=True,
			pe_unit_quantity=5,  # obligatorio porque es traslado total
		)
		self.DocRelObj.create({
			'picking_id': picking.id,
			'codigo_documento': '50',
			'numero_documento': '118-2026-10-123456',
		})
		picking._validar_indicadores_y_contenedores()

	# ------------------------------------------------------------------
	# ERR-3621 - Contenedor y bultos mutuamente excluyentes
	# ------------------------------------------------------------------

	def test_err_3621_contenedor_y_bultos_juntos_falla(self):
		"""Contenedor + pe_unit_quantity > 0 simultáneo debe fallar."""
		picking = self._crear_picking(
			pe_transfer_code='01',
			pe_unit_quantity=5,
		)
		self.ContObj.create({
			'picking_id': picking.id,
			'numero_contenedor': 'TCKU1234567',
		})
		with self.assertRaisesRegex(UserError, 'simultáneamente contenedores'):
			picking._validar_indicadores_y_contenedores()

	def test_solo_contenedor_sin_bultos_pasa(self):
		"""Picking con solo contenedor (sin pe_unit_quantity)."""
		picking = self._crear_picking(
			pe_transfer_code='01',
			pe_unit_quantity=0,
		)
		self.ContObj.create({
			'picking_id': picking.id,
			'numero_contenedor': 'TCKU1234567',
			'numero_precinto': 'PRECINTO-001',
		})
		picking._validar_indicadores_y_contenedores()

	def test_solo_bultos_sin_contenedor_pasa(self):
		"""Picking con solo bultos (sin contenedor)."""
		picking = self._crear_picking(
			pe_transfer_code='01',
			pe_unit_quantity=5,
		)
		picking._validar_indicadores_y_contenedores()

	# ------------------------------------------------------------------
	# ERR-3631 - Traslado total + doc 50/52: bultos obligatorios SOLO si no
	# hay contenedor (Excel 20/06/2026). El contenedor está permitido.
	# ------------------------------------------------------------------

	def _crear_picking_dam(self, motivo, traslado_total, bultos):
		picking = self._crear_picking(
			pe_transfer_code=motivo,
			pe_traslado_total_dam=traslado_total,
			pe_unit_quantity=bultos,
		)
		regimen = {'08': '10', '09': '40', '19': '20'}[motivo]
		self.DocRelObj.create({
			'picking_id': picking.id,
			'codigo_documento': '50',
			'numero_documento': '118-2026-%s-123456' % regimen,
		})
		return picking

	def test_err_3631_traslado_total_con_contenedor_pasa(self):
		"""Motivo 08 + doc 50 + traslado total + contenedor con precinto = OK.

		Hasta 19.0.4.18 esta combinación se rechazaba por una lectura
		errónea del ERR-3631; el ERR-3422 la contempla expresamente.
		"""
		picking = self._crear_picking_dam('08', True, 0)
		self.ContObj.create({
			'picking_id': picking.id,
			'numero_contenedor': 'TCKU1234567',
			'numero_precinto': 'PRECINTO-001',
		})
		picking._validar_indicadores_y_contenedores()

	def test_err_3631_traslado_total_sin_bultos_falla(self):
		"""Traslado total sin bultos ni contenedor falla."""
		picking = self._crear_picking_dam('08', True, 0)
		with self.assertRaisesRegex(UserError, 'ERR-3631'):
			picking._validar_indicadores_y_contenedores()

	# ------------------------------------------------------------------
	# ERR-3632 - Parcial → contenedor o bultos obligatorio
	# ------------------------------------------------------------------

	def test_err_3632_parcial_sin_contenedor_ni_bultos_falla(self):
		picking = self._crear_picking_dam('08', False, 0)
		with self.assertRaisesRegex(UserError, 'ERR-3632'):
			picking._validar_indicadores_y_contenedores()

	def test_parcial_con_contenedor_pasa(self):
		"""Motivo 08 parcial con contenedor y sin precinto: el ERR-3422 no
		alcanza a 08/19 sin traslado total, así que pasa."""
		picking = self._crear_picking_dam('08', False, 0)
		self.ContObj.create({
			'picking_id': picking.id,
			'numero_contenedor': 'TCKU1234567',
		})
		picking._validar_indicadores_y_contenedores()

	def test_parcial_con_bultos_pasa(self):
		picking = self._crear_picking_dam('08', False, 3)
		picking._validar_indicadores_y_contenedores()

	# ------------------------------------------------------------------
	# ERR-3419 - Motivo 09 (exportación), misma lógica que 3631/3632
	# ------------------------------------------------------------------

	def test_err_3419_exportacion_sin_contenedor_ni_bultos_falla(self):
		picking = self._crear_picking_dam('09', True, 0)
		with self.assertRaisesRegex(UserError, 'ERR-3419'):
			picking._validar_indicadores_y_contenedores()

	def test_err_3419_exportacion_con_bultos_pasa(self):
		picking = self._crear_picking_dam('09', True, 120)
		picking._validar_indicadores_y_contenedores()

	# ------------------------------------------------------------------
	# ERR-3422 - Precinto obligatorio con contenedor
	# ------------------------------------------------------------------

	def test_err_3422_exportacion_contenedor_sin_precinto_falla(self):
		"""Motivo 09, sin traslado total, contenedor sin precinto = error."""
		picking = self._crear_picking_dam('09', False, 0)
		self.ContObj.create({
			'picking_id': picking.id,
			'numero_contenedor': 'TCKU1234567',
		})
		with self.assertRaisesRegex(UserError, 'ERR-3422'):
			picking._validar_indicadores_y_contenedores()

	def test_err_3422_importacion_total_sin_precinto_falla(self):
		"""Motivo 08 + traslado total + contenedor sin precinto = error."""
		picking = self._crear_picking_dam('08', True, 0)
		self.ContObj.create({
			'picking_id': picking.id,
			'numero_contenedor': 'TCKU1234567',
		})
		with self.assertRaisesRegex(UserError, 'ERR-3422'):
			picking._validar_indicadores_y_contenedores()

	def test_err_3422_no_aplica_con_manifiesto_carga(self):
		"""Con el indicador de manifiesto de carga el precinto no se exige."""
		picking = self._crear_picking_dam('09', False, 0)
		picking.pe_traslado_contenedor_mc = True
		self.ContObj.create({
			'picking_id': picking.id,
			'numero_contenedor': 'TCKU1234567',
		})
		picking._validar_indicadores_y_contenedores()

	# ------------------------------------------------------------------
	# ERR-3420 / ERR-3421 - Máximo dos contenedores, sin repetidos
	# ------------------------------------------------------------------

	def test_err_3420_tres_contenedores_falla(self):
		picking = self._crear_picking(pe_transfer_code='01', pe_unit_quantity=0)
		for numero in ('TCKU1234567', 'TCKU1234568', 'TCKU1234569'):
			self.ContObj.create({
				'picking_id': picking.id,
				'numero_contenedor': numero,
				'numero_precinto': 'P-1',
			})
		with self.assertRaisesRegex(UserError, 'ERR-3420'):
			picking._validar_indicadores_y_contenedores()

	def test_err_3421_contenedor_repetido_falla(self):
		picking = self._crear_picking(pe_transfer_code='01', pe_unit_quantity=0)
		for numero in ('TCKU1234567', 'tcku1234567'):
			self.ContObj.create({
				'picking_id': picking.id,
				'numero_contenedor': numero,
				'numero_precinto': 'P-1',
			})
		with self.assertRaisesRegex(UserError, 'ERR-3421'):
			picking._validar_indicadores_y_contenedores()

	# ------------------------------------------------------------------
	# Relleno de bultos: el bug bloqueante de 19.0.4.18
	# ------------------------------------------------------------------

	def _preparar_para_validate_eguide(self, picking):
		"""Completa lo que validate_eguide() exige aparte de contenedores."""
		campo = self.env['res.partner']._fields['l10n_pe_district']
		distrito = self.env[campo.comodel_name].sudo().search(
			[('code', '=', '150101')], limit=1)
		if not distrito:
			self.skipTest('Sin ubigeos l10n_pe cargados')
		direcciones = (
			self.partner_cliente,
			picking.picking_type_id.warehouse_id.partner_id,
		)
		for partner in direcciones:
			partner.write({'street': 'Av. Prueba 123', 'l10n_pe_district': distrito.id})
		if not self.partner_cliente.doc_number:
			self.skipTest('El partner de prueba no expone doc_number')
		# Modalidad 01 sin registro de vehículos: validate_eguide() no exige
		# flota propia y el foco del test queda en el relleno de bultos.
		picking.write({
			'pe_transport_mode': '01',
			'pe_carrier_id': self.partner_emisor_doc.id,
			'pe_delivery_date': picking.pe_date_issue,
		})

	def test_validate_eguide_no_rellena_bultos_con_contenedor(self):
		"""Contenedor + bultos en cero debe pasar validate_eguide() sin que el
		relleno por defecto ponga 1 y dispare el ERR-3621."""
		picking = self._crear_picking(pe_transfer_code='01', pe_unit_quantity=0)
		self.ContObj.create({
			'picking_id': picking.id,
			'numero_contenedor': 'TCKU1234567',
			'numero_precinto': 'PRECINTO-001',
		})
		self._preparar_para_validate_eguide(picking)
		picking.validate_eguide()
		self.assertEqual(picking.pe_unit_quantity, 0)

	def test_validate_eguide_rellena_bultos_sin_contenedor(self):
		"""Sin contenedores, bultos vacíos se completan con 1 (comportamiento
		histórico que se conserva)."""
		picking = self._crear_picking(pe_transfer_code='01', pe_unit_quantity=0)
		self._preparar_para_validate_eguide(picking)
		picking.validate_eguide()
		self.assertEqual(picking.pe_unit_quantity, 1)

	def test_completar_bultos_respeta_contenedores(self):
		"""El relleno de button_validate deja bultos en cero si hay contenedor."""
		picking = self._crear_picking(pe_transfer_code='01', pe_unit_quantity=7)
		self.ContObj.create({
			'picking_id': picking.id,
			'numero_contenedor': 'TCKU1234567',
		})
		picking._completar_bultos_desde_movimientos()
		self.assertEqual(picking.pe_unit_quantity, 0)
