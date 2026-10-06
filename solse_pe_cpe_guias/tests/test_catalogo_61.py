# -*- coding: utf-8 -*-

from odoo.tests import tagged

from odoo.addons.solse_pe_cpe_guias.hooks import CATALOGO_61

from .common import TestGuiaCommon


@tagged('post_install', '-at_install', 'solse_pe_cpe_guias')
class TestCatalogo61(TestGuiaCommon):
	"""Verifica que el Catálogo 61 SUNAT esté cargado correctamente
	después de la instalación o migración del módulo.
	"""

	def test_total_codigos_catalogo_61_cargados(self):
		"""El catálogo 61 SUNAT debe tener 30 códigos cargados."""
		registros = self.PeDatas.search([
			('table_code', '=', 'PE.CPE.CATALOG61'),
		])
		self.assertGreaterEqual(
			len(registros), len(CATALOGO_61),
			f"Esperados al menos {len(CATALOGO_61)} códigos en CATALOG61"
		)

	def test_codigos_nuevos_01_06_2026_cargados(self):
		"""Códigos 92-95 publicados el 01/06/2026 deben existir."""
		for codigo in ('92', '93', '94', '95'):
			registro = self.PeDatas.search([
				('code', '=', codigo),
				('table_code', '=', 'PE.CPE.CATALOG61'),
			], limit=1)
			self.assertTrue(
				registro,
				f"Código {codigo} (nuevo 01/06/2026) no existe en CATALOG61"
			)

	def test_codigo_92_cita_terminal_portuario(self):
		"""Código 92 debe ser 'Cita/Orden Entrega Mercancías Terminal Portuario'."""
		registro = self.PeDatas.search([
			('code', '=', '92'),
			('table_code', '=', 'PE.CPE.CATALOG61'),
		], limit=1)
		self.assertTrue(registro)
		self.assertIn('TERMINAL PORTUARIO', registro.name.upper())

	def test_codigos_clasicos_cargados(self):
		"""Códigos pre-existentes (Factura=01, DAM=50, Manifiesto=91) ok."""
		for codigo, palabra_clave in [
			('01', 'FACTURA'),
			('03', 'BOLETA'),
			('50', 'DAM'),
			('52', ''),  # DS - solo verificamos existencia
			('91', 'MANIFIESTO'),
		]:
			registro = self.PeDatas.search([
				('code', '=', codigo),
				('table_code', '=', 'PE.CPE.CATALOG61'),
			], limit=1)
			self.assertTrue(
				registro, f"Código {codigo} no encontrado en CATALOG61"
			)
			if palabra_clave:
				self.assertIn(palabra_clave, registro.name.upper())

	def test_get_selection_devuelve_catalogo_61(self):
		"""El método get_selection del modelo devuelve el catálogo correcto."""
		selecciones = self.PeDatas.get_selection('PE.CPE.CATALOG61')
		codigos = {codigo for codigo, _ in selecciones}

		# Debe contener los 4 nuevos códigos
		self.assertIn('92', codigos)
		self.assertIn('93', codigos)
		self.assertIn('94', codigos)
		self.assertIn('95', codigos)

	def test_unicidad_codigo_por_table_code(self):
		"""No deben existir códigos duplicados en CATALOG61
		(constraint table_code_uniq en pe.datas)."""
		registros = self.PeDatas.search([
			('table_code', '=', 'PE.CPE.CATALOG61'),
		])
		codigos = registros.mapped('code')
		self.assertEqual(
			len(codigos), len(set(codigos)),
			"Hay códigos duplicados en CATALOG61"
		)
