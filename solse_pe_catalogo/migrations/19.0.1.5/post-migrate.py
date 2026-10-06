# -*- coding: utf-8 -*-
"""Post-migración 19.0.1.5 — solse_pe_catalogo.

Las dos secciones de datos que toca este lote van con `noupdate="1"`, así que
la carga del XML no altera lo ya sembrado. Lo de abajo es lo que arregla las
bases existentes.

**M-2 (segunda parte)** · 159 códigos de `PE.TABLA34` del sector 03 traían
coerción float del import original: `1010.0` en vez de `1010`. SUNAT no
reconoce esos códigos. No tienen consumidor hoy —el wizard de asignación mapea
códigos alfanuméricos del sector `ALL`— pero lo tendrán en cuanto alguien
trabaje ese sector.

**M-3 (ampliado)** · El catálogo 51 ofrecía ocho códigos retirados por SUNAT.
Se desactivan en vez de borrarse: puede haber comprobantes antiguos que los
referencien, y un `unlink` los rompería. Los dieciséis que faltaban son
xmlids nuevos y los crea la carga normal del XML.
"""
import logging

_logger = logging.getLogger(__name__)

CATALOGO_51_RETIRADOS = ('0102', '0103', '0110', '0111',
						 '0120', '0121', '0122', '0303')


def migrate(cr, version):
	cr.execute(
		"SELECT 1 FROM information_schema.tables WHERE table_name = 'pe_datas'")
	if not cr.fetchone():
		return

	# ------------------------------------------------ M-2 · TABLA34
	cr.execute(r"""
		UPDATE pe_datas
		SET code = left(code, length(code) - 2)
		WHERE table_code = 'PE.TABLA34'
		  AND code ~ '^[0-9]+\.0$'
	""")
	if cr.rowcount:
		_logger.info(
			"solse_pe_catalogo: %s código(s) de PE.TABLA34 corregidos "
			"(se les quitó el «.0» de la coerción float).", cr.rowcount)

	# ------------------------------------------------ M-3 · catálogo 51
	cr.execute("""
		SELECT id, code, name FROM pe_datas
		WHERE table_code = 'PE.CPE.CATALOG51'
		  AND code IN %s AND active = TRUE
		ORDER BY code
	""", (CATALOGO_51_RETIRADOS,))
	retirados = cr.fetchall()
	if retirados:
		cr.execute("""
			UPDATE pe_datas SET active = FALSE
			WHERE table_code = 'PE.CPE.CATALOG51' AND code IN %s
		""", (CATALOGO_51_RETIRADOS,))
		_logger.warning(
			"solse_pe_catalogo: %s código(s) del catálogo 51 desactivados por "
			"estar retirados del catálogo oficial de SUNAT: %s. Si algún "
			"comprobante los usa, SUNAT lo rechaza — revíselos.",
			len(retirados),
			', '.join('%s (%s)' % (c, (n or '')[:40]) for _, c, n in retirados))
