# -*- coding: utf-8 -*-

import logging

_logging = logging.getLogger(__name__)


# Catálogo 61 SUNAT — Tipos de documento relacionado a Guía de Remisión
# Fuente: Anexo Catálogo 61 publicado por SUNAT.
# Códigos 92-95 agregados en la publicación del 01/06/2026.
CATALOGO_61 = [
	('01', 'FACTURA'),
	('03', 'BOLETA DE VENTA'),
	('04', 'LIQUIDACION DE COMPRA'),
	('07', 'NOTA DE CREDITO'),
	('08', 'NOTA DE DEBITO'),
	('09', 'GUIA DE REMISION REMITENTE'),
	('12', 'TICKET DE MAQUINA REGISTRADORA'),
	('13', 'DOCUMENTO EMITIDO POR BANCOS, INSTITUCIONES FINANCIERAS, CREDITICIAS Y DE SEGUROS'),
	('14', 'RECIBO POR SERVICIOS PUBLICOS DE SUMINISTRO DE ENERGIA ELECTRICA, AGUA, TELEFONO, TELEX Y TELEGRAFICOS'),
	('20', 'COMPROBANTE DE RETENCION'),
	('40', 'COMPROBANTE DE PERCEPCION'),
	('48', 'COMPROBANTE DE OPERACIONES - LEY N° 29972'),
	('49', 'CONSTANCIA DE DEPOSITO - IVAP (LEY 28211)'),
	('50', 'DECLARACION ADUANERA DE MERCANCIAS (DAM)'),
	('52', 'DECLARACION SIMPLIFICADA (DS)'),
	('71', 'GUIA DE REMISION REMITENTE COMPLEMENTARIA AL CPE'),
	('72', 'GUIA DE REMISION TRANSPORTISTA COMPLEMENTARIA AL CPE'),
	('73', 'DOCUMENTO PARA ATRIBUCION DE CREDITO FISCAL'),
	('74', 'CONSTANCIA DE DEPOSITO SPOT - DETRACCION'),
	('75', 'TICKET DE SALIDA'),
	('76', 'ACTA DE INVENTARIO'),
	('77', 'GUIA DE TRANSITO'),
	('78', 'AUTORIZACION DE TRANSITO'),
	('80', 'NOTA DE CONTABILIDAD'),
	('81', 'CARTA DE PORTE AEREO'),
	('91', 'MANIFIESTO DE CARGA'),
	('92', 'CITA/ORDEN ENTREGA MERCANCIAS DEL TERMINAL PORTUARIO'),
	('93', 'DOCUMENTO ZOFRATACNA'),
	('94', 'SOLICITUD TRASLADO - ZED'),
	('95', 'SOLICITUD DE TRASLADO - ZOFRATACNA'),
]


def _cargar_catalogo_61(env):
	"""Carga el Catálogo 61 SUNAT (tipos de documento relacionado a GRE)
	en el modelo `pe.datas` con `table_code = PE.CPE.CATALOG61`.

	Idempotente: solo crea registros faltantes; no toca los existentes.
	"""
	pe_datas = env['pe.datas'].sudo()
	creados, omitidos = 0, 0
	for codigo, nombre in CATALOGO_61:
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
		"Catálogo 61 SUNAT cargado: %d nuevos, %d ya existían",
		creados, omitidos
	)


def post_init_hook(env):
	"""Hook ejecutado al instalar el módulo por primera vez."""
	_cargar_catalogo_61(env)
