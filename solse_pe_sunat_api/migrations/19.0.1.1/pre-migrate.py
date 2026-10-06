# -*- coding: utf-8 -*-
"""Pre-migración 19.0.1.1 — L2: detección de duplicados antes de revivir la
constraint de unicidad.

Las _sql_constraints estaban MUERTAS en Odoo 19 (el ORM las ignora con un
warning: odoo/orm/model_classes.py:162-164), así que la base puede contener
duplicados que la constraint revivida no admitirá. Y en v19 una constraint
que falla NO aborta la actualización: se degrada a warning de esquema y no
se aplica (odoo/orm/registry.py::post_constraint — «not a deployment
showstopper»), con lo que el defecto se volvería invisible.

Este script hace el fallo VISIBLE Y BLOQUEANTE: si hay duplicados, detiene
la actualización nombrándolos, para que se resuelvan a mano ANTES. No borra
nada.
"""
import logging
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

COMPROBACIONES = [
	("solse_sunat_api", ['company_id', 'tipo'], "las credenciales API SUNAT")
]


def migrate(cr, version):
	for tabla, columnas, etiqueta in COMPROBACIONES:
		cr.execute("SELECT 1 FROM information_schema.tables WHERE table_name = %s", (tabla,))
		if not cr.fetchone():
			continue
		cols = ', '.join(columnas)
		cr.execute(
			"SELECT {cols}, count(*) FROM {tabla} GROUP BY {cols} HAVING count(*) > 1".format(
				cols=cols, tabla=tabla))
		duplicados = cr.fetchall()
		if duplicados:
			detalle = '\n'.join('  - ({}) x{}'.format(
				', '.join(str(v) for v in fila[:-1]), fila[-1]) for fila in duplicados)
			raise UserError(
				'No se puede actualizar: {etiqueta} tiene registros duplicados '
				'que la restricción de unicidad ({cols}) no admite. '
				'Resolverlos a mano y reintentar. Duplicados:\n{detalle}'.format(
					etiqueta=etiqueta, cols=cols, detalle=detalle))
		_logger.info('L2 pre-migrate: %s sin duplicados en (%s).', tabla, cols)
