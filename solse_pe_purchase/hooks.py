# -*- coding: utf-8 -*-

import logging

_logger = logging.getLogger(__name__)


# Mapeo afectación → cómo distribuir en columnas SIRE 8.4 al detectar cada concepto.
# Cada entrada: (concepto, col_base, col_imp, es_defecto)
#   concepto: clave del dict que devuelve _detectar_taxes_por_concepto()
#   col_base: nro_col donde sumar la base imponible (None si no aplica)
#   col_imp:  nro_col donde sumar el monto del impuesto (None si no aplica)
#   es_defecto: si True, la línea se vincula al M2M impuesto_defecto_ids
MAPEO_AFECTACIONES = {
	'gravada_dg': [
		('igv_dg',  15, 16, True),
		('icbper',  None, 23, False),
		('isc',     None, 22, False),
	],
	'gravada_dgng': [
		('igv_dgng', 17, 18, True),
		('icbper',   None, 23, False),
		('isc',      None, 22, False),
	],
	'gravada_dng': [
		('igv_dng', 19, 20, True),
		('icbper',  None, 23, False),
		('isc',     None, 22, False),
	],
	'exonerada':   [('exonerado', 21, None, True)],
	'inafecta':    [('inafecto',  21, None, True)],
	'importacion': [('igv_dg', 15, 16, True)],  # importación usa el IGV destinado a gravadas
	'no_domiciliado': [],
	'excluir':        [],
}

XMLID_POR_CATEGORIA = {
	'gravada_dg':     'solse_pe_purchase.afectacion_gravada_dg',
	'gravada_dgng':   'solse_pe_purchase.afectacion_gravada_dgng',
	'gravada_dng':    'solse_pe_purchase.afectacion_gravada_dng',
	'exonerada':      'solse_pe_purchase.afectacion_exonerada',
	'inafecta':       'solse_pe_purchase.afectacion_inafecta',
	'importacion':    'solse_pe_purchase.afectacion_importacion',
	'no_domiciliado': 'solse_pe_purchase.afectacion_no_domiciliado',
	'excluir':        'solse_pe_purchase.afectacion_excluir',
}

# Patrones de clasificación de IGV por nombre (case-insensitive, ya normalizado a MAYÚSCULAS).
# Orden de evaluación importante: DGNG primero porque sus patrones son más específicos.
PATRONES_IGV_DGNG = ['G NG', 'GNG', 'G Y NG', 'GRAV Y NO GRAV', 'MIXT', 'PRORRAT']
PATRONES_IGV_DNG = [' NG', 'NO GRAV', 'SIN CRED', 'SIN CREDITO']


def _clasificar_igv(taxes_igv):
	"""Clasifica un recordset de account.tax (todos IGV) en tres recordsets:
	(dg, dgng, dng) según patrones en el nombre.

	Si solo hay un IGV en taxes_igv, queda como DG y los otros dos vacíos
	(el caller decide el fallback).
	"""
	if not taxes_igv:
		return taxes_igv, taxes_igv, taxes_igv

	dg = taxes_igv.browse()
	dgng = taxes_igv.browse()
	dng = taxes_igv.browse()

	for tax in taxes_igv:
		nombre = ' '.join((tax.name or '').upper().split())  # normalizar espacios

		# DGNG primero (patrones más específicos: contiene G+NG)
		if any(p in nombre for p in PATRONES_IGV_DGNG):
			dgng |= tax
		# DNG: contiene NG aislado o "no grav" / "sin crédito"
		elif any(p in nombre for p in PATRONES_IGV_DNG):
			dng |= tax
		else:
			dg |= tax

	return dg, dgng, dng


def _detectar_taxes_por_concepto(env, compania):
	"""Detecta los account.tax de la compañía para cada concepto SUNAT.

	Para IGV, además clasifica los candidatos en DG/DGNG/DNG por nombre.
	Si una sub-categoría queda vacía, se usa el primer IGV como fallback
	(asegura que las 3 afectaciones gravadas queden con un IGV asignado
	aunque sea el mismo).

	Heurísticas en cascada para encontrar IGV (primer match con resultados gana):
	  1. l10n_pe_edi_tax_code='1000'
	  2. name ilike 'IGV' + amount entre 17 y 19
	  3. tax_group_id.name ilike 'IGV'
	"""
	Tax = env['account.tax']
	dom_base = [
		('type_tax_use', '=', 'purchase'),
		('company_id', '=', compania.id),
	]

	def _buscar(codigo_sunat, palabras_nombre, palabras_group, rango_monto=None):
		# 1) Por código formal SUNAT, si está configurado.
		if codigo_sunat and 'l10n_pe_edi_tax_code' in Tax._fields:
			r = Tax.search(dom_base + [('l10n_pe_edi_tax_code', '=', codigo_sunat)])
			if r:
				return r
		# 2) Por nombre + (opcional) rango de monto.
		for palabra in palabras_nombre:
			d = dom_base + [('name', 'ilike', palabra)]
			if rango_monto:
				d += [('amount', '>=', rango_monto[0]), ('amount', '<=', rango_monto[1])]
			r = Tax.search(d)
			if r:
				return r
		# 3) Por tax_group_id.name.
		for palabra in palabras_group:
			r = Tax.search(dom_base + [('tax_group_id.name', 'ilike', palabra)])
			if r:
				return r
		return Tax.browse()

	# IGV: detectar todos los candidatos y luego clasificar
	todos_igv = _buscar('1000', ['IGV'], ['IGV'], rango_monto=(17.0, 19.0))
	igv_dg, igv_dgng, igv_dng = _clasificar_igv(todos_igv)

	# Fallback: si alguna sub-categoría quedó vacía, usar el primer IGV "general" (DG)
	# o el primero de todos los detectados.
	primer_igv = igv_dg[:1] or todos_igv[:1]
	if not igv_dg:
		igv_dg = primer_igv
	if not igv_dgng:
		igv_dgng = primer_igv
	if not igv_dng:
		igv_dng = primer_igv

	return {
		'igv_dg':    igv_dg,
		'igv_dgng':  igv_dgng,
		'igv_dng':   igv_dng,
		'icbper':    _buscar('7152', ['ICBPER'],                 ['ICBPER']),
		'isc':       _buscar('2000', ['ISC'],                    ['ISC']),
		'exonerado': _buscar('9997', ['Exonerad', 'Exo'],        ['Exonerad']),
		'inafecto':  _buscar('9998', ['Inafect', 'Ina'],         ['Inafect']),
	}


def _aplicar_configuracion_afectaciones(env, compania, taxes_por_concepto, reemplazar=False):
	"""Crea/actualiza las líneas de impuesto en cada afectación.

	Args:
		env: environment de Odoo
		compania: res.company
		taxes_por_concepto: dict {'igv_dg': recordset, 'igv_dgng': recordset, ...}
			Cada recordset debe tener exactamente UN account.tax (el elegido).
		reemplazar: si True, borra las líneas existentes antes de crear.
			Si False, solo opera sobre afectaciones con impuesto_afect_ids vacía.

	Returns:
		Tupla (afectaciones_configuradas, afectaciones_omitidas)
	"""
	Impuesto = env['solse.pe.impuesto.afectacion.compra']
	configuradas = env['solse.pe.afectacion.compra']
	omitidas = env['solse.pe.afectacion.compra']

	for categoria, config in MAPEO_AFECTACIONES.items():
		xmlid = XMLID_POR_CATEGORIA.get(categoria)
		if not xmlid:
			continue
		afectacion = env.ref(xmlid, raise_if_not_found=False)
		if not afectacion:
			continue
		if not config:
			continue

		if reemplazar and afectacion.impuesto_afect_ids:
			afectacion.impuesto_afect_ids.unlink()

		# A-12 (L3): las afectaciones son GLOBALES (sin company_id) y lo
		# per-compañía son los account.tax de sus líneas. La semántica
		# correcta en multiempresa es AÑADIR las líneas de los impuestos de
		# esta compañía si aún no están — no omitir la afectación entera
		# porque otra compañía ya la pobló. Una línea "ya existe" si hay
		# otra con el mismo impuesto, columna y base de cálculo.
		existentes = {
			(li.impuesto_id.id, li.nro_col_importe_impuesto, li.toma_para_calculo)
			for li in afectacion.impuesto_afect_ids
		}
		agregado = False

		ids_para_defecto = []
		for concepto, col_base, col_imp, es_defecto in config:
			recordset = taxes_por_concepto.get(concepto)
			tax = recordset[:1] if recordset else None
			if not tax:
				continue

			linea_base = None
			if col_base and (tax.id, col_base, 'base') in existentes:
				linea_base = afectacion.impuesto_afect_ids.filtered(
					lambda li: li.impuesto_id.id == tax.id
					and li.nro_col_importe_impuesto == col_base
					and li.toma_para_calculo == 'base')[:1]
			elif col_base:
				linea_base = Impuesto.create({
					'linea_afectacion_id': afectacion.id,
					'impuesto_id': tax.id,
					'nro_col_importe_impuesto': col_base,
					'toma_para_calculo': 'base',
				})
				agregado = True
			if col_imp and (tax.id, col_imp, 'impuesto') in existentes:
				linea_imp = afectacion.impuesto_afect_ids.filtered(
					lambda li: li.impuesto_id.id == tax.id
					and li.nro_col_importe_impuesto == col_imp
					and li.toma_para_calculo == 'impuesto')[:1]
				if es_defecto:
					ids_para_defecto.append(linea_imp.id)
			elif col_imp:
				linea_imp = Impuesto.create({
					'linea_afectacion_id': afectacion.id,
					'impuesto_id': tax.id,
					'nro_col_importe_impuesto': col_imp,
					'toma_para_calculo': 'impuesto',
				})
				agregado = True
				if es_defecto:
					ids_para_defecto.append(linea_imp.id)
			elif col_base and es_defecto and linea_base:
				ids_para_defecto.append(linea_base.id)

		if ids_para_defecto:
			# (4, id): ENLAZA sin reemplazar — los defectos de otras
			# compañías se conservan; el consumidor filtra por compañía.
			afectacion.write({'impuesto_defecto_ids': [
				(4, id_linea) for id_linea in ids_para_defecto
				if id_linea not in afectacion.impuesto_defecto_ids.ids]})

		if not agregado and not reemplazar:
			omitidas |= afectacion
			continue

		configuradas |= afectacion
		_logger.info(
			"[%s] Afectación '%s' configurada con %d líneas de impuesto.",
			compania.name, afectacion.name, len(afectacion.impuesto_afect_ids),
		)

	return configuradas, omitidas


def _post_init_hook(env):
	"""Ejecutado al instalar el módulo. Intenta autoconfigurar las afectaciones
	usando heurísticas. Si no encuentra impuestos para algún concepto, deja la
	afectación vacía (el usuario puede usar el wizard manual desde el menú).
	"""
	companias = env['res.company'].search([])
	for compania in companias:
		taxes = _detectar_taxes_por_concepto(env, compania)
		# Considerar "encontrado" sólo si hay algo distinto al fallback genérico
		if not any(taxes.values()):
			_logger.warning(
				"[%s] No se detectaron impuestos peruanos. Las afectaciones quedan "
				"vacías; el usuario debe completarlas con el asistente desde "
				"Configuración → Asistente: Configurar afectaciones.",
				compania.name,
			)
			continue
		_aplicar_configuracion_afectaciones(env, compania, taxes, reemplazar=False)
