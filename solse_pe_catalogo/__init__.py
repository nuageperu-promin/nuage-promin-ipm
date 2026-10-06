# -*- coding: utf-8 -*-

from . import models


def post_init_hook(env):
	"""Carga los porcentajes de detraccion al instalar.

	Sin ellos, todo comprobante con detraccion sale con monto cero y SUNAT
	lo rechaza con el error 3037. Ver `models/porcentajes_spot.py`.
	"""
	from .models.porcentajes_spot import cargar_porcentajes
	cargar_porcentajes(env)
