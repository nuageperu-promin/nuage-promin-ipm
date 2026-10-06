# -*- coding: utf-8 -*-
"""Post-migración 19.0.1.4 — rellenar porcentajes de los códigos nuevos.

Los registros 002/027/038/041 recién sembrados (o adoptados de un registro
manual por el pre-migrate) llevan porcentaje cero. cargar_porcentajes()
solo escribe donde hay cero, así que no pisa tasas ajustadas a mano.
"""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
	env = api.Environment(cr, SUPERUSER_ID, {})
	from odoo.addons.solse_pe_catalogo.models.porcentajes_spot import (
		cargar_porcentajes)
	resultado = cargar_porcentajes(env)
	_logger.info(
		'solse_pe_catalogo post-migrate 19.0.1.4: porcentajes SPOT '
		'rellenados: %s', resultado)
