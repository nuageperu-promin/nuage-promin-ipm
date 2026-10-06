# -*- coding: utf-8 -*-

import logging

from odoo import api, models

from .. import hooks

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
	_inherit = 'res.company'

	@api.model_create_multi
	def create(self, vals_list):
		"""A-12 (L3): las compañías creadas DESPUÉS de instalar el módulo
		también reciben sus afectaciones de compra.

		El hook de instalación solo cubre las compañías existentes en ese
		momento; sin este override, una compañía nueva quedaba con el
		conjunto vacío y el RCE salía con las columnas en cero.

		Secuencia — verificada contra el nativo: `account` difiere la carga
		del plan contable (y por tanto de los impuestos) a un callback de
		PRECOMMIT (`account/models/company.py:478-488`). Configurar aquí
		directamente encontraría cero impuestos. Se encola la configuración
		en la misma cola de precommit DESPUÉS de llamar a super(): los
		callbacks corren en orden de inserción, así que el nuestro corre con
		el plan contable ya cargado.
		"""
		companias = super().create(vals_list)
		for compania in companias:
			def _configurar_afectaciones(compania=compania):
				env = self.env
				taxes = hooks._detectar_taxes_por_concepto(env, compania)
				if not any(taxes.values()):
					_logger.warning(
						"[%s] Compañía nueva sin impuestos peruanos "
						"detectables: las afectaciones de compra quedan "
						"pendientes del asistente manual (Configuración → "
						"Asistente: Configurar afectaciones).",
						compania.name)
					return
				hooks._aplicar_configuracion_afectaciones(
					env, compania, taxes, reemplazar=False)
			self.env.cr.precommit.add(_configurar_afectaciones)
		return companias
