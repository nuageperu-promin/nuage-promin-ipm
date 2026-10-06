# -*- coding: utf-8 -*-

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import TestGuiaCommon


@tagged('post_install', '-at_install', 'solse_pe_cpe_guias')
class TestSubregimen1992(TestGuiaCommon):
	"""Tests para el sub-régimen Motivo 19 + Doc 92 (Traslado mercancía
	extranjera con Cita/Orden del Terminal Portuario).
	Cubre: campo computado + restricciones cliente-side.
	"""

	def test_subregimen_activo_con_motivo_19_y_doc_92(self):
		"""La propiedad computada se activa solo con motivo 19 + doc 92."""
		picking = self._crear_picking(pe_transfer_code='19')
		self.DocRelObj.create({
			'picking_id': picking.id,
			'codigo_documento': '92',
			'numero_documento': 'CITA-001',
			'emisor_id': self.partner_terminal_portuario.id,
		})
		picking.invalidate_recordset()
		self.assertTrue(picking.pe_es_subregimen_19_92)

	def test_subregimen_no_activo_con_motivo_19_pero_doc_50(self):
		"""Motivo 19 con doc 50 (DAM) NO activa sub-régimen."""
		picking = self._crear_picking(pe_transfer_code='19')
		self.DocRelObj.create({
			'picking_id': picking.id,
			'codigo_documento': '50',
			'numero_documento': '118-2026-10-123456',
		})
		picking.invalidate_recordset()
		self.assertFalse(picking.pe_es_subregimen_19_92)

	def test_subregimen_no_activo_con_doc_92_pero_motivo_diferente(self):
		"""Doc 92 con motivo distinto a 19 NO activa sub-régimen.
		Esto NO debería poder ocurrir en producción porque ERR-3613
		bloquea la combinación, pero validamos la lógica del compute.
		"""
		picking = self._crear_picking(pe_transfer_code='01')
		# Saltamos la validación de motivo+tipo para probar solo el compute
		self.env.cr.execute("""
			INSERT INTO pe_stock_documento_relacionado
			(picking_id, codigo_documento, numero_documento, sequence)
			VALUES (%s, '92', 'CITA-001', 10)
		""", (picking.id,))
		picking.invalidate_recordset()
		self.assertFalse(picking.pe_es_subregimen_19_92)

	def test_subregimen_no_acepta_contenedor(self):
		"""En sub-régimen 19+92 no se permite registrar contenedor."""
		picking = self._crear_picking(pe_transfer_code='19')
		self.DocRelObj.create({
			'picking_id': picking.id,
			'codigo_documento': '92',
			'numero_documento': 'CITA-001',
			'emisor_id': self.partner_terminal_portuario.id,
		})
		self.ContObj.create({
			'picking_id': picking.id,
			'numero_contenedor': 'TCKU1234567',
		})
		picking.invalidate_recordset()
		with self.assertRaisesRegex(UserError, 'sub-régimen.*no se debe.*contenedor'):
			picking._validar_indicadores_y_contenedores()

	def test_subregimen_ignora_bultos_sin_error(self):
		"""En sub-régimen 19+92 los bultos del usuario son ignorados
		(no se envían al XML) y no generan error de validación."""
		picking = self._crear_picking(
			pe_transfer_code='19',
			pe_unit_quantity=99,  # se ignora
		)
		self.DocRelObj.create({
			'picking_id': picking.id,
			'codigo_documento': '92',
			'numero_documento': 'CITA-001',
			'emisor_id': self.partner_terminal_portuario.id,
		})
		picking.invalidate_recordset()
		# No debe levantar
		picking._validar_indicadores_y_contenedores()
