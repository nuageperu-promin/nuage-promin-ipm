# -*- coding: utf-8 -*-
"""L-6 · Las secuencias de este módulo, una por compañía.

En archivo APARTE y no dentro de `res_company.py`: ese ya existe y tiene
campos del módulo. Añadir aquí evita tocarlo.

En esta suite no hay secuencias globales para comprobantes electrónicos:
cada empresa lleva su correlativo. Una `ir.sequence` cargada desde `data/`
sin `company_id` no queda global —el campo toma la compañía instaladora—,
así que `next_by_code` desde una segunda empresa no la encuentra. Trampa 22
de `migrar-modulo-v17-a-v19.md`.

Aditivo: el registro del `data/` se queda como la secuencia de la compañía
que instaló, y esto crea las que falten. Ningún correlativo en marcha se
toca: son números ya enviados a SUNAT.
"""
from odoo import api, models


class Company(models.Model):
	_inherit = 'res.company'

	@api.model
	def pe_asegurar_secuencias_guias_todas(self):
		"""Todas las compañías. La invoca el `<function>` del data, que
		exige `@api.model` (trampa 17)."""
		self.env['res.company'].sudo().search([]).pe_asegurar_secuencias_guias()

	def pe_asegurar_secuencias_guias(self):
		# Con el formato del data/ (L-6b, corrida 2 de MULTIEMPRESA): la
		# numeración exige T + 3 alfanuméricos + correlativo
		# (ValidacionesGRE; la regex de stock.py:969); sin prefijo la
		# secuencia rendía «1» y la guía no se podía numerar.
		for compania in self._pe_companias_con_cpe():
			compania.pe_asegurar_secuencia(
				'pe.eguide.sync', 'Guía de Remisión Electrónica',
				prefix='T001-', padding=5)
			compania.pe_asegurar_secuencia(
				'pe.eguide.cancel', 'Anulación de Guía de Remisión',
				prefix='EG01-')
