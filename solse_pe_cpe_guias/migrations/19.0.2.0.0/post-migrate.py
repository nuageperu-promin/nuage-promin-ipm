# -*- coding: utf-8 -*-

# Migración 19.0.2.0.0 - SUNAT 01/06/2026
# 1) Carga el Catálogo 61 SUNAT (incluye códigos nuevos 92-95).
# 2) Migra los datos legacy (pe_is_realeted / pe_related_*) al
#    nuevo One2many pe_documento_relacionado_ids.
#
# Mapeo legacy → Catálogo 61: el campo pe_related_code apuntaba al
# PE.CPE.CATALOG21 que tiene un dominio distinto al catálogo SUNAT 61.
# Se hace un best-effort mapping de los códigos comunes; los códigos
# sin equivalencia clara se registran en log para revisión manual.

import logging

_logging = logging.getLogger(__name__)


# Mapeo del catálogo legacy CATALOG21 (mal usado) al catálogo SUNAT real 61.
# CATALOG21 contenía:
#   01 NUMERACION DAM        → 50 DECLARACION ADUANERA DE MERCANCIAS (DAM)
#   02 NUMERO ORDEN ENTREGA  → sin equivalencia directa en cat 61
#   03 NUMERO DE SCOP        → sin equivalencia directa en cat 61
#   04 MANIFIESTO DE CARGA   → 91 MANIFIESTO DE CARGA
#   05 CONSTANCIA DETRACCION → 49 CONSTANCIA DE DEPOSITO (DETRACCION)
#   06 OTROS                 → sin equivalencia directa en cat 61
MAPEO_LEGACY_A_CAT61 = {
	'01': '50',
	'04': '91',
	'05': '49',
}


def migrate(cr, version):
	if not version:
		return

	from odoo import api, SUPERUSER_ID
	env = api.Environment(cr, SUPERUSER_ID, {})

	# 1) Catálogo 61 (mismo loader que post_init_hook).
	from odoo.addons.solse_pe_cpe_guias.hooks import _cargar_catalogo_61
	_cargar_catalogo_61(env)

	# 2) Migración de datos legacy.
	pickings = env['stock.picking'].search([
		('pe_is_realeted', '=', True),
		('pe_related_number', '!=', False),
	])
	_logging.info(
		"Migración 19.0.2.0.0: %d guías con documento relacionado legacy",
		len(pickings)
	)

	creados, omitidos = 0, 0
	sin_mapeo = []

	for picking in pickings:
		# Si ya tiene registros en el One2many, no duplicamos.
		if picking.pe_documento_relacionado_ids:
			omitidos += 1
			continue
		if not picking.pe_related_code or not picking.pe_related_number:
			omitidos += 1
			continue

		codigo_nuevo = MAPEO_LEGACY_A_CAT61.get(picking.pe_related_code)
		if not codigo_nuevo:
			# Sin mapeo confiable - registrar para revisión manual.
			sin_mapeo.append((picking.id, picking.name, picking.pe_related_code))
			omitidos += 1
			continue

		env['pe.stock.documento.relacionado'].create({
			'picking_id': picking.id,
			'codigo_documento': codigo_nuevo,
			'numero_documento': picking.pe_related_number,
			# emisor_id queda vacío - el usuario debe completarlo manualmente
			# si el código requiere RUC (01, 03, 04, 09, 12, 48, 92).
		})
		creados += 1

	_logging.info(
		"Migración legacy → Cat 61: %d creados, %d omitidos",
		creados, omitidos
	)
	if sin_mapeo:
		_logging.warning(
			"Migración legacy: %d guías sin mapeo confiable al catálogo 61. "
			"Revisar manualmente:",
			len(sin_mapeo)
		)
		for pid, nombre, cod in sin_mapeo[:50]:
			_logging.warning("  Picking %s (id=%d) - código legacy: %s",
							 nombre, pid, cod)
		if len(sin_mapeo) > 50:
			_logging.warning("  ... y %d más", len(sin_mapeo) - 50)
