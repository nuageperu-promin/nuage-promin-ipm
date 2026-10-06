# -*- coding: utf-8 -*-
"""Pre-migración 19.0.1.4 — solse_pe_catalogo.

QA-7: el seed del catálogo 54 no traía los códigos 002, 027, 038 y 041
(presentes en la tabla autoritativa del propio módulo,
models/porcentajes_spot.py). Quien necesitó el 027 —«Flete local», 4%— lo
creó A MANO.

Este script ADOPTA esos registros manuales: si existe una fila de pe_datas
con (code, table_code) de los códigos nuevos y SIN ir_model_data, se le
crea la entrada de ir_model_data con el xmlid del seed. Así la carga del
XML no intenta crear un duplicado (la constraint lo impediría) y el
registro manual pasa a ser el oficial. Los valores manuales se conservan
(noupdate); el porcentaje lo normaliza cargar_porcentajes() en el
post-migrate si estaba en cero.
"""
import logging

_logger = logging.getLogger(__name__)

ADOPTABLES = {
	'002': 'pe_cpe_catalog54_37',
	'027': 'pe_cpe_catalog54_38',
	'038': 'pe_cpe_catalog54_39',
	'041': 'pe_cpe_catalog54_40',
}


def migrate(cr, version):
	cr.execute(
		"SELECT 1 FROM information_schema.tables WHERE table_name = 'pe_datas'")
	if not cr.fetchone():
		return
	for codigo, xmlid in ADOPTABLES.items():
		cr.execute(
			"""
			SELECT d.id
			FROM pe_datas d
			LEFT JOIN ir_model_data imd
			  ON imd.model = 'pe.datas' AND imd.res_id = d.id
			WHERE d.code = %s AND d.table_code = 'PE.CPE.CATALOG54'
			  AND imd.id IS NULL
			ORDER BY d.id
			LIMIT 1
			""", (codigo,))
		fila = cr.fetchone()
		if not fila:
			continue
		cr.execute(
			"""
			INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
			VALUES ('solse_pe_catalogo', %s, 'pe.datas', %s, TRUE)
			ON CONFLICT DO NOTHING
			""", (xmlid, fila[0]))
		_logger.info(
			"solse_pe_catalogo pre-migrate: registro manual del catálogo 54 "
			"código %s adoptado como %s (id %s).", codigo, xmlid, fila[0])
