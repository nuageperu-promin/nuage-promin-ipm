# -*- coding: utf-8 -*-
# Catálogos del Anexo 2 de la Planilla Electrónica y utilidades de formato
# para los archivos de importación del PDT PLAME.

import re
import unicodedata

# ── Tabla 3: Tipo de documento de identidad ─────────────────────────────
# Solo se listan los códigos habilitados para PRESTADOR DE SERVICIOS.
# El código 11 (partida de nacimiento) fue deshabilitado el 19.05.2013.
TABLA_3_TIPO_DOCUMENTO = [
	('01', '01 - Documento Nacional de Identidad'),
	('04', '04 - Carné de Extranjería'),
	('06', '06 - Registro Único de Contribuyentes'),
	('07', '07 - Pasaporte'),
	('09', '09 - Carné de Solicitud de Refugio'),
	('22', '22 - Carné de Identidad - Relaciones Exteriores'),
	('23', '23 - Permiso Temporal de Permanencia'),
	('24', '24 - Documento de Identidad Extranjero'),
	('26', '26 - Carné de Permiso Temporal de Permanencia'),
]

# ── Tabla 23: Tipo de comprobante del PS 4ta categoría ──────────────────
# OJO: la nota de crédito es 'N', NO 'C'. Verificado contra el Anexo 2
# oficial (tablas paramétricas vigentes).
TABLA_23_TIPO_COMPROBANTE = [
	('R', 'R - Recibo por honorarios'),
	('N', 'N - Nota de crédito'),
	('D', 'D - Dieta'),
	('O', 'O - Otro comprobante'),
]

# ── Tabla 25: Convenios para evitar la doble tributación ────────────────
TABLA_25_CONVENIO = [
	('0', '0 - Ninguno'),
	('1', '1 - Canadá'),
	('2', '2 - Chile'),
	('3', '3 - CAN'),
	('4', '4 - Brasil'),
	('5', '5 - México'),
	('6', '6 - Corea'),
	('7', '7 - Suiza'),
	('8', '8 - Portugal'),
]

# ── Régimen pensionario del prestador (Ley 29903) ───────────────────────
# Campo 10 de la Estructura 20. Los archivos aceptados por el PDT en
# producción lo envían VACÍO, por eso el vacío es una opción válida y es
# el valor por defecto del módulo.
REGIMEN_PENSIONARIO = [
	('', 'Vacío (no informar)'),
	('1', '1 - ONP'),
	('2', '2 - SPP'),
	('3', '3 - Sin retención / No aplica'),
]

# Códigos SUNAT de tipo de documento que corresponden a un recibo por
# honorarios y a su nota de crédito (catálogo 01 de comprobantes).
CODIGO_SUNAT_RECIBO_HONORARIOS = '02'
CODIGO_SUNAT_NOTA_CREDITO = '07'

# Terminador de campo de los archivos de importación. No es un separador:
# cada campo, incluido el último, va seguido de este carácter.
TERMINADOR_CAMPO = '|'
FIN_DE_LINEA = '\r\n'

# Umbral a partir del cual corresponde retener renta de 4ta categoría
# cuando el prestador no cuenta con constancia de suspensión vigente.
UMBRAL_RETENCION_CUARTA = 1500.0


def quitar_tildes(texto):
	"""Devuelve el texto sin tildes ni caracteres no ASCII.

	Los archivos que el PDT acepta en producción son ASCII puro, por lo que
	se normaliza antes de escribir.
	"""
	if not texto:
		return ''
	descompuesto = unicodedata.normalize('NFKD', str(texto))
	sin_tildes = ''.join(c for c in descompuesto if not unicodedata.combining(c))
	return sin_tildes.encode('ascii', 'ignore').decode('ascii')


def normalizar_texto(texto, longitud=None):
	"""Limpia un texto para escribirlo en el archivo: sin tildes, en
	mayúsculas, sin el carácter terminador y con espacios colapsados."""
	limpio = quitar_tildes(texto).upper()
	limpio = limpio.replace(TERMINADOR_CAMPO, ' ')
	limpio = re.sub(r'\s+', ' ', limpio).strip()
	if longitud:
		limpio = limpio[:longitud]
	return limpio


def formato_monto(valor):
	"""Formatea un importe tal como lo hace el PDT en los archivos válidos.

	Se usa punto decimal, sin separador de miles, y se suprimen los
	decimales cuando son cero (750 en lugar de 750.00).
	"""
	valor = round(float(valor or 0.0), 2)
	texto = '%.2f' % valor
	entero, decimales = texto.split('.')
	if decimales == '00':
		return entero
	return texto


def formato_fecha(fecha):
	"""Formatea una fecha como dd/mm/aaaa."""
	if not fecha:
		return ''
	return fecha.strftime('%d/%m/%Y')


def armar_linea(campos):
	"""Une los campos agregando el terminador a cada uno, incluido el último."""
	return ''.join('%s%s' % (campo or '', TERMINADOR_CAMPO) for campo in campos)


def partir_serie_numero(referencia):
	"""Separa una referencia tipo 'E001-75' en (serie, numero).

	Devuelve (False, False) si la referencia no tiene el formato esperado.
	El número se devuelve sin ceros a la izquierda, que es como lo emiten
	los archivos aceptados por el PDT.
	"""
	if not referencia:
		return False, False
	texto = quitar_tildes(referencia).upper().strip()
	coincidencia = re.match(r'^([A-Z0-9]{1,4})\s*-\s*(\d{1,20})$', texto)
	if not coincidencia:
		return False, False
	serie = coincidencia.group(1)
	numero = coincidencia.group(2).lstrip('0') or '0'
	return serie, numero
