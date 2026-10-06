# -*- coding: utf-8 -*-

import logging

_logging = logging.getLogger(__name__)


# Códigos del Catálogo 61 SUNAT que aplican exclusivamente a la Guía de
# Remisión Transportista y que NO carga solse_pe_cpe_guias (su hook solo
# trae los que usa la GRR).
CATALOGO_61_TRANSPORTISTA = [
	('31', 'GUIA DE REMISION TRANSPORTISTA'),
	('65', 'AUTORIZACION DE CIRCULACION PARA TRANSPORTAR MATPEL - CALLAO'),
	('66', 'AUTORIZACION DE CIRCULACION PARA TRANSPORTE DE CARGA Y MERCANCIAS EN LIMA METROPOLITANA'),
	('67', 'PERMISO DE OPERACION ESPECIAL PARA EL SERVICIO DE TRANSPORTE DE MATPEL - MTC'),
	('68', 'HABILITACION SANITARIA DE TRANSPORTE TERRESTRE DE PRODUCTOS PESQUEROS Y ACUICOLAS'),
	('69', 'PERMISO / AUTORIZACION DE OPERACION DE TRANSPORTE DE MERCANCIAS'),
]


def _cargar_catalogo_61_transportista(env):
	"""Agrega al `pe.datas` los códigos del Catálogo 61 propios de la GRT.

	Idempotente: solo crea los registros faltantes, no toca los que ya
	cargó el hook de solse_pe_cpe_guias.
	"""
	pe_datas = env['pe.datas'].sudo()
	creados, omitidos = 0, 0
	for codigo, nombre in CATALOGO_61_TRANSPORTISTA:
		existente = pe_datas.search([
			('code', '=', codigo),
			('table_code', '=', 'PE.CPE.CATALOG61'),
		], limit=1)
		if existente:
			omitidos += 1
			continue
		pe_datas.create({
			'code': codigo,
			'name': nombre,
			'table_code': 'PE.CPE.CATALOG61',
		})
		creados += 1
	_logging.info(
		"Catálogo 61 SUNAT (GRT) cargado: %d nuevos, %d ya existían",
		creados, omitidos
	)


def post_init_hook(env):
	"""Hook ejecutado al instalar el módulo por primera vez."""
	_cargar_catalogo_61_transportista(env)
