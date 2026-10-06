# -*- coding: utf-8 -*-

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import TestGuiaCommon


@tagged('post_install', '-at_install', 'solse_pe_cpe_guias')
class TestDocumentosRelacionados(TestGuiaCommon):
	"""Tests para validaciones SUNAT 01/06/2026 de documentos relacionados.
	Cubre: constraints del modelo + ERR-3445, ERR-3493, ERR-3612, ERR-3613.
	"""

	# ------------------------------------------------------------------
	# Constraints del modelo pe.stock.documento.relacionado
	# ------------------------------------------------------------------

	def test_emisor_obligatorio_para_tipo_01_factura(self):
		"""ERR-3380: emisor (RUC) requerido para doc tipo 01-Factura."""
		picking = self._crear_picking(pe_transfer_code='02')
		with self.assertRaises(ValidationError):
			self.DocRelObj.create({
				'picking_id': picking.id,
				'codigo_documento': '01',
				'numero_documento': 'F001-1',
				# emisor_id ausente
			})

	def test_emisor_obligatorio_para_tipo_92_terminal_portuario(self):
		"""ERR-3614: emisor (RUC) requerido para doc tipo 92."""
		picking = self._crear_picking(pe_transfer_code='19')
		with self.assertRaises(ValidationError):
			self.DocRelObj.create({
				'picking_id': picking.id,
				'codigo_documento': '92',
				'numero_documento': 'CITA-001',
			})

	def test_emisor_no_obligatorio_para_tipo_49_detraccion(self):
		"""Tipo 49 (Constancia Detracción) no requiere emisor."""
		picking = self._crear_picking(pe_transfer_code='09')
		registro = self.DocRelObj.create({
			'picking_id': picking.id,
			'codigo_documento': '49',
			'numero_documento': '000000001',
		})
		self.assertFalse(registro.emisor_requerido)

	def test_formato_invalido_doc_factura_falla(self):
		"""ERR-3441: número de factura debe cumplir formato F001-12345678."""
		picking = self._crear_picking(pe_transfer_code='02')
		with self.assertRaises(ValidationError):
			self.DocRelObj.create({
				'picking_id': picking.id,
				'codigo_documento': '01',
				'numero_documento': 'TEXTO-INVALIDO',
				'emisor_id': self.partner_emisor_doc.id,
			})

	# ------------------------------------------------------------------
	# Validaciones SUNAT por motivo
	# ------------------------------------------------------------------

	def test_motivo_19_sin_docs_falla(self):
		"""ERR-3493: motivo 19 requiere al menos doc 50/52/91/92."""
		picking = self._crear_picking(pe_transfer_code='19')
		with self.assertRaisesRegex(UserError, 'motivo de traslado 19'):
			picking._validar_documentos_relacionados()

	def test_motivo_19_con_doc_50_pasa(self):
		"""Motivo 19 con DAM (50) cumple ERR-3493."""
		picking = self._crear_picking(pe_transfer_code='19')
		self.DocRelObj.create({
			'picking_id': picking.id,
			'codigo_documento': '50',
			'numero_documento': '118-2026-10-123456',
		})
		# No debe levantar
		picking._validar_documentos_relacionados()

	def test_motivo_19_con_dos_docs_92_falla(self):
		"""ERR-3612: solo un doc tipo 92 permitido para motivo 19."""
		picking = self._crear_picking(pe_transfer_code='19')
		self.DocRelObj.create({
			'picking_id': picking.id,
			'codigo_documento': '92',
			'numero_documento': 'CITA-001',
			'emisor_id': self.partner_terminal_portuario.id,
		})
		self.DocRelObj.create({
			'picking_id': picking.id,
			'codigo_documento': '92',
			'numero_documento': 'CITA-002',
			'emisor_id': self.partner_terminal_portuario.id,
		})
		with self.assertRaisesRegex(UserError, 'Solo se permite una.*92'):
			picking._validar_documentos_relacionados()

	def test_motivo_19_doc_92_con_doc_50_falla(self):
		"""ERR-3613: doc 92 no coexiste con docs 50/52/91."""
		picking = self._crear_picking(pe_transfer_code='19')
		self.DocRelObj.create({
			'picking_id': picking.id,
			'codigo_documento': '92',
			'numero_documento': 'CITA-001',
			'emisor_id': self.partner_terminal_portuario.id,
		})
		self.DocRelObj.create({
			'picking_id': picking.id,
			'codigo_documento': '50',
			'numero_documento': '118-2026-10-123456',
		})
		with self.assertRaisesRegex(UserError, 'tipo 92.*no puede coexistir'):
			picking._validar_documentos_relacionados()

	def test_motivo_13_con_doc_52_falla(self):
		"""Cambio 01/06/2026: motivo 13 ya NO permite tipo 52 (DS)."""
		picking = self._crear_picking(pe_transfer_code='13')
		self.DocRelObj.create({
			'picking_id': picking.id,
			'codigo_documento': '52',
			'numero_documento': '118-2026-20-123456',
		})
		with self.assertRaisesRegex(UserError, 'motivo 13.*52.*no es permitido'):
			picking._validar_documentos_relacionados()

	def test_motivo_08_con_doc_invalido_falla(self):
		"""ERR-3445: motivo 08 solo permite docs 09/49/50/52/80."""
		picking = self._crear_picking(pe_transfer_code='08')
		self.DocRelObj.create({
			'picking_id': picking.id,
			'codigo_documento': '01',
			'numero_documento': 'F001-1',
			'emisor_id': self.partner_emisor_doc.id,
		})
		with self.assertRaisesRegex(UserError, 'motivo 08'):
			picking._validar_documentos_relacionados()

	def test_doc_91_solo_para_motivo_19_falla(self):
		"""Doc 91 (Manifiesto) en motivos distintos a 19 debe fallar."""
		picking = self._crear_picking(pe_transfer_code='01')
		self.DocRelObj.create({
			'picking_id': picking.id,
			'codigo_documento': '91',
			'numero_documento': 'MANIF-001',
		})
		with self.assertRaisesRegex(UserError, '91 y 92 solo.*motivo.*19'):
			picking._validar_documentos_relacionados()

	def test_multiples_docs_valido_motivo_09(self):
		"""Motivo 09 (importación) acepta múltiples docs DAM + Constancia."""
		picking = self._crear_picking(pe_transfer_code='09')
		self.DocRelObj.create({
			'picking_id': picking.id,
			'codigo_documento': '50',
			'numero_documento': '118-2026-10-123456',
		})
		self.DocRelObj.create({
			'picking_id': picking.id,
			'codigo_documento': '49',
			'numero_documento': '000000001',
		})
		# No debe levantar
		picking._validar_documentos_relacionados()
