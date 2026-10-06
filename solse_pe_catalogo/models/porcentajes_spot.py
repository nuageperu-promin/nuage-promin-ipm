# -*- coding: utf-8 -*-

"""Porcentajes de detraccion del catalogo 54 (SPOT).

Por que existe este archivo
---------------------------
Los registros del catalogo 54 se cargaban con `value = 0.0` en TODOS los
codigos. La consecuencia no es que la detraccion salga mal: es que sale
**cero**, y con cero el comprobante se rechaza.

	monto_detraccion = importe * (detraccion_id.value / 100.0) if
					   detraccion_id.value > 0 else 0.0

Con `value = 0`, el XML lleva `<cbc:Amount>0.00</cbc:Amount>` y SUNAT
responde el error **3037** — «El dato ingresado en monto de detraccion no
cumple con el formato establecido»— porque su regla exige *decimal positivo
**mayor a cero**, de 12 enteros y hasta 2 decimales* (hoja «Factura2_0» de
las reglas de validacion, campo 106).

El mensaje habla del formato y el problema es el valor, asi que el
diagnostico desde el lado del cliente es practicamente imposible.

Sobre la vigencia
-----------------
Estas tasas las fija SUNAT por Resolucion de Superintendencia y **cambian
sin previo aviso**. Las de aqui corresponden a los anexos 1, 2 y 3 de la
R.S. 183-2004/SUNAT con sus modificatorias, contrastadas en agosto de 2026.
Antes de una implementacion conviene verificarlas en:

	https://orientacion.sunat.gob.pe/apendices-del-sistema-de-detracciones

Un porcentaje desactualizado no rompe la emision —el comprobante se acepta—
pero deposita de menos, y eso le cuesta al cliente el credito fiscal de la
operacion mas una multa del 50% de lo no depositado.
"""

import logging

_logger = logging.getLogger(__name__)


# codigo del catalogo 54 -> (porcentaje, descripcion abreviada)
PORCENTAJES_SPOT = {
	# --- Anexo 1: bienes, se aplica sobre 1/2 UIT
	'001': (10.0, 'Azúcar y melaza de caña'),
	'002': (3.85, 'Arroz pilado (IVAP)'),
	'003': (10.0, 'Alcohol etílico'),
	'007': (10.0, 'Caña de azúcar'),
	# --- Anexo 2: bienes
	'004': (4.0,  'Recursos hidrobiológicos'),
	'005': (4.0,  'Maíz amarillo duro'),
	'008': (4.0,  'Madera'),
	'009': (10.0, 'Arena y piedra'),
	'010': (15.0, 'Residuos, subproductos, desechos, recortes y desperdicios'),
	'011': (10.0, 'Bienes gravados con IGV por renuncia a la exoneración'),
	'014': (4.0,  'Carnes y despojos comestibles'),
	'016': (10.0, 'Aceite de pescado'),
	'017': (4.0,  'Harina, polvo y pellets de pescado'),
	'023': (4.0,  'Leche'),
	'031': (10.0, 'Oro gravado con el IGV'),
	'032': (10.0, 'Páprika y otros frutos de los géneros capsicum o pimienta'),
	'034': (10.0, 'Minerales metálicos no auríferos'),
	'035': (1.5,  'Bienes exonerados del IGV'),
	'036': (1.5,  'Oro y demás minerales metálicos exonerados del IGV'),
	'039': (10.0, 'Minerales no metálicos'),
	'041': (15.0, 'Plomo'),
	# --- Anexo 3: servicios y contratos de construcción, sobre S/ 700
	'012': (12.0, 'Intermediación laboral y tercerización'),
	'019': (10.0, 'Arrendamiento de bienes'),
	'020': (12.0, 'Mantenimiento y reparación de bienes muebles'),
	'021': (10.0, 'Movimiento de carga'),
	'022': (12.0, 'Otros servicios empresariales'),
	'024': (10.0, 'Comisión mercantil'),
	'025': (10.0, 'Fabricación de bienes por encargo'),
	'026': (10.0, 'Servicio de transporte de personas'),
	'027': (4.0,  'Servicio de transporte de bienes por vía terrestre'),
	'030': (4.0,  'Contratos de construcción'),
	'037': (12.0, 'Demás servicios gravados con el IGV'),
	'040': (4.0,  'Primera venta de inmuebles gravados con el IGV'),
}

# Codigos DEROGADOS segun la tabla 5.4 del instructivo de deposito masivo
# (SUNAT, febrero 2021). No se les asigna porcentaje: si aparecieran con uno,
# alguien podria seleccionarlos y generar un deposito que el Banco de la
# Nacion rechaza.
CODIGOS_DEROGADOS = {
	'006': 'Algodón — hasta el 31/12/2014',
	'013': 'Animales vivos — hasta el 08/01/2005',
	'015': 'Abonos, cueros y pieles de origen animal — hasta el 08/01/2005',
	'018': 'Embarcaciones pesqueras — hasta el 31/12/2014',
	'029': 'Algodón en rama sin desmotar — hasta el 31/12/2014',
	'033': 'Espárragos — hasta el 31/12/2014',
	'038': 'Espectáculos públicos no deportivos — hasta el 31/12/2014',
}

TABLA = 'PE.CPE.CATALOG54'


def cargar_porcentajes(env, forzar=False):
	"""Escribe los porcentajes en los registros del catalogo 54.

	Por defecto solo toca los que estan en cero, para no pisar una tasa que
	el cliente haya ajustado a mano —puede tener razon: las tasas cambian y
	su contador puede ir por delante de nuestra tabla—. Con `forzar` se
	reescriben todos.
	"""
	Datas = env['pe.datas'].sudo()
	actualizados, ausentes = [], []

	for codigo, (porcentaje, descripcion) in PORCENTAJES_SPOT.items():
		registro = Datas.search([
			('code', '=', codigo),
			('table_code', '=', TABLA),
		], limit=1)
		if not registro:
			ausentes.append(codigo)
			continue
		if registro.value and not forzar:
			continue
		if registro.value == porcentaje:
			continue
		registro.value = porcentaje
		actualizados.append('%s=%s%%' % (codigo, porcentaje))

	if actualizados:
		_logger.info('SOLSE · porcentajes de detracción cargados (%s): %s',
					 len(actualizados), ', '.join(actualizados))
	if ausentes:
		_logger.warning('SOLSE · códigos del catálogo 54 que no existen en '
						'esta base: %s', ', '.join(ausentes))

	# Los derogados se desactivan en lugar de dejarlos seleccionables: con un
	# codigo fuera de vigencia el Banco de la Nacion rechaza el deposito.
	desactivados = 0
	if 'active' in Datas._fields:
		obsoletos = Datas.search([
			('code', 'in', list(CODIGOS_DEROGADOS)),
			('table_code', '=', TABLA),
			('active', '=', True),
		])
		if obsoletos:
			obsoletos.write({'active': False})
			desactivados = len(obsoletos)
			_logger.info('SOLSE · %s código(s) de detracción derogados '
						 'desactivados', desactivados)

	return {'actualizados': len(actualizados), 'ausentes': len(ausentes),
			'derogados': desactivados}
