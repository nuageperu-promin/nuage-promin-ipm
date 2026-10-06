# -*- coding: utf-8 -*-

"""
Migración 19.0.0.1 → 19.0.0.2 — Normalización de sequence_prefix

La versión anterior del módulo sobreescribía _compute_split_sequence y guardaba
sequence_prefix SIN el guión ('F001' en lugar de 'F001-'). Eso rompía la búsqueda
de últimos correlativos, causando que el preview siempre mostrara el correlativo
inicial y que ir.sequence.next_by_id() no se invocara al postear (el super
nativo veía move_has_name=True porque el preview estaba escrito en name).

Esta migración:
  1. Fuerza el recompute de sequence_prefix / sequence_number para facturas con
	  tipo de documento de prefijo personalizado. El nuevo compute (nativo, vía
	  regex _sequence_fixed_regex) guarda 'F001-' con guión.
  2. Limpia borradores legacy cuyo name quedó fijado con un preview incorrecto.
	  Solo se tocan borradores que nunca fueron posted, para no perder nombres
	  editados manualmente.
"""
import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
	env = api.Environment(cr, SUPERUSER_ID, {})

	# ---------------------------------------------------------------
	# 1) Recompute de sequence_prefix / sequence_number para moves con
	#    prefijo personalizado (posted y no posted).
	# ---------------------------------------------------------------
	moves_a_recomputar = env['account.move'].sudo().search([
		('l10n_latam_document_type_id.usar_prefijo_personalizado', '=', True),
		('name', '!=', '/'),
		('name', '!=', False),
	])

	if moves_a_recomputar:
		_logger.info(
			"[solse_pe_edi] Recomputando sequence_prefix/sequence_number "
			"para %d facturas con prefijo personalizado",
			len(moves_a_recomputar),
		)
		# modified() marca los campos dependientes como stale; el siguiente
		# acceso o flush los recomputa usando el compute actual (nativo).
		moves_a_recomputar.modified(['name'])
		env.flush_all()

	# ---------------------------------------------------------------
	# 2) Limpiar borradores con name legacy (preview del bug anterior).
	#    Solo borradores que NUNCA fueron posted, para no pisar nombres
	#    que el usuario haya editado manualmente.
	# ---------------------------------------------------------------
	borradores_legacy = env['account.move'].sudo().search([
		('state', '=', 'draft'),
		('posted_before', '=', False),
		('l10n_latam_document_type_id.usar_prefijo_personalizado', '=', True),
		('name', '!=', '/'),
		('name', '!=', False),
	])

	if borradores_legacy:
		_logger.info(
			"[solse_pe_edi] Reseteando name a '/' en %d borradores con "
			"preview legacy (se recalcularán via name_placeholder nativo)",
			len(borradores_legacy),
		)
		# Escritura directa en BD para evitar disparar todos los computes
		# asociados a account.move (son costosos y estos borradores no
		# tienen pagos conciliados ni estado posted_before).
		cr.execute("""
			UPDATE account_move
			SET name = '/', sequence_prefix = NULL, sequence_number = 0
			WHERE id = ANY(%s)
		""", [borradores_legacy.ids])

	_logger.info("[solse_pe_edi] Migración 19.0.0.2 completada.")
