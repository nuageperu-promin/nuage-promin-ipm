# -*- coding: utf-8 -*-

import requests
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging
_logger = logging.getLogger(__name__)

STATE = [('ACTIVO', 'ACTIVO'),
		 ('BAJA DE OFICIO', 'BAJA DE OFICIO'),
		 ('BAJA DEFINITIVA', 'BAJA DEFINITIVA'),
		 ('BAJA PROVISIONAL', 'BAJA PROVISIONAL'),
		 ('SUSPENSION TEMPORAL', 'BAJA PROVISIONAL'),
		 ('INHABILITADO-VENT.UN', 'INHABILITADO-VENT.UN'),
		 ('BAJA MULT.INSCR. Y O', 'BAJA MULT.INSCR. Y O'),
		 ('PENDIENTE DE INI. DE', 'PENDIENTE DE INI. DE'),
		 ('OTROS OBLIGADOS', 'OTROS OBLIGADOS'),
		 ('NUM. INTERNO IDENTIF', 'NUM. INTERNO IDENTIF'),
		 ('ANUL.PROVI.-ACTO ILI', 'ANUL.PROVI.-ACTO ILI'),
		 ('ANULACION - ACTO ILI', 'ANULACION - ACTO ILI'),
		 ('BAJA PROV. POR OFICI', 'BAJA PROV. POR OFICI'),
		 ('ANULACION - ERROR SU', 'ANULACION - ERROR SU')]

CONDITION = [('HABIDO', 'HABIDO'),
			 ('NO HABIDO', 'NO HABIDO'),
			 ('NO HALLADO', 'NO HALLADO'),
			 ('PENDIENTE', 'PENDIENTE'),
			 ('NO HALLADO SE MUDO D', 'NO HALLADO SE MUDO D'),
			 ('NO HALLADO NO EXISTE', 'NO HALLADO NO EXISTE'),
			 ('NO HALLADO FALLECIO', 'NO HALLADO FALLECIO'),
			 ('-', 'NO HABIDO'),
			 ('NO HALLADO OTROS MOT', 'NO HALLADO OTROS MOT'),
			 ('NO APLICABLE', 'NO APLICABLE'),
			 ('NO HALLADO NRO.PUERT', 'NO HALLADO NRO.PUERT'),
			 ('NO HALLADO CERRADO', 'NO HALLADO CERRADO'),
			 ('POR VERIFICAR', 'POR VERIFICAR'),
			 ('NO HALLADO DESTINATA', 'NO HALLADO DESTINATA'),
			 ('NO HALLADO RECHAZADO', 'NO HALLADO RECHAZADO')]

# ::::::::::::::::: Usando API de APIPERU.dev

def get_dni_apiperu(token, dni):
	endpoint = "https://apiperu.dev/api/dni/%s" % dni
	headers = {
		"Authorization": "Bearer %s" % token,
		"Content-Type": "application/json",
	}
	try:
		datos_dni = requests.get(endpoint, data={}, headers=headers, timeout=10)
		if datos_dni.status_code == 200:
			datos = datos_dni.json()
			return datos['data']['nombre_completo']
		else:
			return ""
	except Exception as e:
		_logger.info('algo salio mal en la busqueda dni con el apiperu')
		_logger.info(e)
		raise UserError('Algo salio mal en la busqueda dni con el apiperu')
		return ""

def get_ruc_apiperu(token, ruc):
	try:
		endpoint = "https://apiperu.dev/api/ruc/%s" % ruc
		headers = {
			"Authorization": "Bearer %s" % token,
			"Content-Type": "application/json",
		}
		datos_ruc = requests.get(endpoint, data={}, headers=headers, timeout=10)
		if datos_ruc.status_code == 200:
			datos_ruc = datos_ruc.json()
			ubigeo = datos_ruc['data']['ubigeo'][2]
			direccion = datos_ruc['data']['direccion_completa'] if 'direccion_completa' in datos_ruc['data'] else ''
			if not direccion:
				direccion = ''
			if not ubigeo:
				ubigeo = '-'
			datos = {
				'error': False, 
				'message': 'ok',
				'condicion': datos_ruc['data']['condicion'],
				'estado': datos_ruc['data']['estado'],
				'ubigeo': ubigeo if ubigeo != "-" else "150101",
				'direccion': direccion.split(',')[0],
				'razonSocial': datos_ruc['data']['nombre_o_razon_social'],
				'ruc': datos_ruc['data']['ruc'],
			}
			if 'es_agente_de_retencion' in datos_ruc['data'] and datos_ruc['data']['es_agente_de_retencion'] == "SI":
				datos['es_agente_retencion'] = True

			if 'es_buen_contribuyente' in datos_ruc['data'] and datos_ruc['data']['es_buen_contribuyente'] == "SI":
				datos['buen_contribuyente'] = True

			return datos
		else:
			return {'error': True, 'message': 'Error al intentar obtener datos'}
	except Exception as e:
		return {'error': True, 'message': str(e)}

# ::::::::::::::::: Usando API de migo.pe
def get_dni_apimigo(token, dni):
	endpoint = "https://api.migo.pe/api/v1/dni/"
	datos_consultar = {
		'dni': dni,
		'token': token
	}
	try:
		datos_dni = requests.post(url=endpoint, data=datos_consultar, timeout=10)
		if datos_dni.status_code == 200:
			datos = datos_dni.json()
			return datos['nombre']
		else:
			return ""
	except Exception as e:
		_logger.info('algo salio mal en la busqueda dni')
		_logger.info(e)
		return ""

def get_ruc_apimigo(token, ruc, datos_generales=True, buen_contribuyente=True, es_agente_retencion=True):
	endpoint = "https://api.migo.pe/api/v1/ruc/"
	datos_consultar = {
		'ruc': ruc,
		'token': token
	}
	datos = {}
	try:
		if datos_generales:
			datos_request = requests.post(url=endpoint, data=datos_consultar)
			if datos_request.status_code == 200:
				datos_ruc = datos_request.json()
				_logger.info("datos de la busqeusqueda")
				_logger.info(datos_ruc)
				ubigeo = datos_ruc['ubigeo']
				direccion = datos_ruc['direccion_simple'] or ''
				datos = {
						'error': False, 
						'message': 'ok',
						'condicion': datos_ruc['condicion_de_domicilio'],
						'estado': datos_ruc['estado_del_contribuyente'],
						'ubigeo': ubigeo if ubigeo != "-" else "150101",
						'direccion': direccion,
						'razonSocial': datos_ruc['nombre_o_razon_social'],
						'ruc': datos_ruc['ruc'],
				}
			else:
				return {'error': True, 'message': 'No se pudo cargar'}


		if not datos:
			datos['error'] = False
			datos['message'] = "ok"

		if buen_contribuyente:
			datos_buen_contribuyente = es_buen_contribuyente(token, ruc)
			if datos_buen_contribuyente['buen_contribuyente']:
				datos['buen_contribuyente'] = datos_buen_contribuyente['buen_contribuyente']
				datos['a_partir_del'] = datos_buen_contribuyente['a_partir_del']
				datos['resolucion'] = datos_buen_contribuyente['resolucion']
			else:
				datos['buen_contribuyente'] = False
				datos['a_partir_del'] = ""
				datos['resolucion'] = ""

		if es_agente_retencion:
			datos_agente_retencion = es_gente_retencion(token, ruc)
			if datos_agente_retencion['es_agente_retencion']:
				datos['es_agente_retencion'] = datos_agente_retencion['es_agente_retencion']
				datos['r_a_partir_del'] = datos_agente_retencion['a_partir_del']
				datos['r_resolucion'] = datos_agente_retencion['resolucion']
			else:
				datos['es_agente_retencion'] = False
				datos['r_a_partir_del'] = ""
				datos['r_resolucion'] = ""

		return datos

	except Exception as e:
		_logger.info('algo salio mal en la busqueda ruc')
		_logger.info(e)
		return {'error': True, 'message': 'No se pudo obtener una respuesta valida'}


def es_buen_contribuyente(token, ruc):
	endpoint = "https://api.migo.pe/api/v1/ruc/buenos-contribuyentes"
	datos_consultar = {
		'ruc': ruc,
		'token': token
	}
	datos = {
		'buen_contribuyente': False,
	}
	try:
		datos_request = requests.post(url=endpoint, data=datos_consultar)
		if datos_request.status_code == 200:
			datos = datos_request.json()
			datos['buen_contribuyente'] = True
			return datos
	except Exception as e:
		pass
	return datos

def es_gente_retencion(token, ruc):
	endpoint = "https://api.migo.pe/api/v1/ruc/agentes-retencion"
	datos_consultar = {
		'ruc': ruc,
		'token': token
	}
	datos = {
		'es_agente_retencion': False,
	}
	try:
		datos_request = requests.post(url=endpoint, data=datos_consultar)
		if datos_request.status_code == 200:
			datos = datos_request.json()
			datos['es_agente_retencion'] = True
			return datos
	except Exception as e:
		pass
	return datos


# ---------------------------------------------------------------------------
# M-52. Aquí abajo había un bloque `"""` de 31 líneas con pruebas de consola
# contra apiperu.dev, y dentro DOS COPIAS de un token real y vivo. No se
# ejecutaba —era una cadena suelta— pero se distribuía con el módulo a cada
# cliente, que es lo mismo que publicarlo.
#
# El bloque se elimina entero. Las pruebas de consola no se versionan; si hace
# falta probar el servicio, el token sale de la compañía:
#
#     compania = env.company
#     datos = get_tipo_cambio_apiperu(compania.token_api, '2020-12-02')
#
# El campo es `res.company.token_api` (solse_pe_vat/models/res_company.py:12),
# con `default=''`, y es de donde ya leen `solse_pe_rate_api` y las búsquedas
# de RUC y DNI. Ninguna credencial debe volver a este archivo.
# ---------------------------------------------------------------------------
