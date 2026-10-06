# -*- coding: utf-8 -*-
"""Post-migración 19.0.1.14 — L4.1: reclasificar el histórico de estados.

Hasta 19.0.1.13, getEstadoSunat mapeaba todo código < 2000 distinto de
cero a '07' Observado — las EXCEPCIONES (0100 «el sistema no puede
responder», 1033 «registrado previamente con otros datos») quedaban
disfrazadas de observaciones, que se declaran. Es el eslabón 5 de C-6.

Se reclasifica desde response_code, que ya está guardado:
  0100-0999 → '15' (reintentable) · 1000-1999 → '17' (no reintentable).
Solo se tocan expedientes hoy en '07' cuyo código lo contradice; los que
no tienen response_code se quedan como están (el plan lo manda así). Se
registra el conteo antes/después para la verificación del lote.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
	cr.execute(
		"SELECT 1 FROM information_schema.tables WHERE table_name = 'solse_cpe'")
	if not cr.fetchone():
		return
	cr.execute(
		"SELECT estado_sunat, count(*) FROM solse_cpe GROUP BY estado_sunat")
	_logger.info("L4.1 reclasificación — ANTES: %s", dict(cr.fetchall()))

	# response_code es texto y puede traer basura: solo dígitos.
	cr.execute(
		"""
		UPDATE solse_cpe
		SET estado_sunat = CASE
			WHEN trim(response_code)::int < 1000 THEN '15'
			ELSE '17'
		END
		WHERE estado_sunat = '07'
		  AND response_code IS NOT NULL
		  AND trim(response_code) ~ '^[0-9]+$'
		  AND trim(response_code)::int BETWEEN 100 AND 1999
		""")
	reclasificados = cr.rowcount

	cr.execute(
		"SELECT estado_sunat, count(*) FROM solse_cpe GROUP BY estado_sunat")
	_logger.info(
		"L4.1 reclasificación — DESPUÉS: %s (%d expedientes movidos de "
		"'07' a '15'/'17')", dict(cr.fetchall()), reclasificados)
