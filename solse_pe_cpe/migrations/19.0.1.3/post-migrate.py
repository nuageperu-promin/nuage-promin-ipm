# -*- coding: utf-8 -*-

"""Deja la validacion estricta DESACTIVADA en las bases que se actualizan.

El campo nace con `default=True` porque es lo que conviene en una
instalacion nueva. Pero activarlo de golpe en una base que ya opera
significaria que facturas que hoy se postean sin problema dejen de
postearse, y eso no lo puede decidir una actualizacion: lo decide quien
conoce el estado de los datos de esa empresa.

Se desactiva en las companias existentes y se deja el aviso en el log. El
usuario lo activa desde Ajustes cuando haya revisado su histórico.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
	if not version:
		# Instalacion nueva: se respeta el default (activado).
		return

	cr.execute("""
		UPDATE res_company
		   SET validacion_estricta_cpe = FALSE
		 WHERE validacion_estricta_cpe IS NOT FALSE
	""")
	_logger.warning(
		'SOLSE · la validación estricta de comprobantes se dejó DESACTIVADA '
		'en %s compañía(s) existentes. Actívala en Ajustes / Configuración '
		'Peruana cuando hayas revisado tus datos: avisa de lo que SUNAT '
		'rechazaría antes de enviar, en lugar de después.', cr.rowcount)
