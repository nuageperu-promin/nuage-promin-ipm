# -*- coding: utf-8 -*-

"""Carga los porcentajes de detraccion en las bases ya instaladas.

Los registros del catalogo 54 se cargaron con `value = 0.0`, y con
porcentaje cero el monto de detraccion sale cero: SUNAT rechaza el
comprobante con el error 3037.

Solo se tocan los que estan en cero. Si alguien ya corrigio un porcentaje a
mano, se respeta: las tasas cambian por resolucion y su contador puede ir
por delante de esta tabla.
"""

import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
	if not version:
		return
	env = api.Environment(cr, SUPERUSER_ID, {})
	from odoo.addons.solse_pe_catalogo.models.porcentajes_spot import (
		cargar_porcentajes)
	resultado = cargar_porcentajes(env)
	_logger.warning(
		'SOLSE · %s porcentaje(s) de detracción cargados. Antes estaban en '
		'cero y cualquier comprobante con detracción era rechazado por SUNAT '
		'con el error 3037. Verificar las tasas en '
		'orientacion.sunat.gob.pe/apendices-del-sistema-de-detracciones antes '
		'de emitir.', resultado.get('actualizados'))
