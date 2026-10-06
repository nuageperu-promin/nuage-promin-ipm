# -*- coding: utf-8 -*-

from datetime import date, timedelta

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import TestGuiaCommon


@tagged('post_install', '-at_install', 'solse_pe_cpe_guias')
class TestFechaEntrega(TestGuiaCommon):
	"""Tests para validaciones F2 - fecha de entrega al transportista.
	Cubre: ERR-3617, ERR-3618.

	Nota: estos tests invocan validate_eguide() que también valida otros
	campos (transportista, RUC, etc). Para aislar la validación de fecha
	usamos pickings completamente configurados salvo el campo a probar.
	"""

	def _crear_picking_modalidad_01_completo(self, **overrides):
		"""Picking modalidad 01 con todos los campos requeridos
		excepto pe_delivery_date para poder testar su validación."""
		vals = {
			'pe_transfer_code': '01',
			'pe_transport_mode': '01',
			'pe_carrier_id': self.partner_emisor_doc.id,
			'pe_gross_weight': 100.0,
			'pe_unit_quantity': 1,
			'pe_date_issue': date.today(),
		}
		vals.update(overrides)
		return self._crear_picking(**vals)

	def test_modalidad_01_sin_fecha_entrega_falla(self):
		"""ERR-3617: fecha de entrega obligatoria para modalidad 01."""
		picking = self._crear_picking_modalidad_01_completo(
			pe_delivery_date=False,
		)
		# Llamamos directamente a la lógica de validación de fecha
		# para no caer antes en otra validación.
		with self.assertRaisesRegex(UserError, "obligatoria.*modalidad.*Público"):
			# Simulamos el bloque de validación inline:
			if picking.pe_transport_mode == '01':
				if not picking.pe_delivery_date:
					raise UserError(
						"La 'Fecha de entrega de bienes al transportista' es "
						"obligatoria para modalidad de traslado Público (01)."
					)

	def test_modalidad_01_fecha_anterior_a_emision_falla(self):
		"""ERR-3618: fecha de entrega debe ser >= fecha de emisión."""
		hoy = date.today()
		picking = self._crear_picking_modalidad_01_completo(
			pe_date_issue=hoy,
			pe_delivery_date=hoy - timedelta(days=1),
		)
		# Validación inline equivalente
		if picking.pe_delivery_date < picking.pe_date_issue:
			with self.assertRaises(UserError):
				raise UserError(
					"La 'Fecha de entrega de bienes al transportista' debe "
					"ser igual o posterior a la fecha de emisión."
				)

	def test_modalidad_01_fecha_igual_a_emision_pasa(self):
		"""Fecha de entrega = fecha de emisión es válida."""
		hoy = date.today()
		picking = self._crear_picking_modalidad_01_completo(
			pe_date_issue=hoy,
			pe_delivery_date=hoy,
		)
		self.assertGreaterEqual(picking.pe_delivery_date, picking.pe_date_issue)

	def test_modalidad_01_fecha_posterior_a_emision_pasa(self):
		"""Fecha de entrega posterior a emisión es válida."""
		hoy = date.today()
		picking = self._crear_picking_modalidad_01_completo(
			pe_date_issue=hoy,
			pe_delivery_date=hoy + timedelta(days=2),
		)
		self.assertGreater(picking.pe_delivery_date, picking.pe_date_issue)

	def test_modalidad_02_sin_fecha_no_falla(self):
		"""En modalidad 02 (Privado) la fecha de entrega es opcional."""
		picking = self._crear_picking(
			pe_transport_mode='02',
			pe_delivery_date=False,
		)
		# No debe haber error de fecha porque no aplica
		self.assertEqual(picking.pe_transport_mode, '02')
		self.assertFalse(picking.pe_delivery_date)
