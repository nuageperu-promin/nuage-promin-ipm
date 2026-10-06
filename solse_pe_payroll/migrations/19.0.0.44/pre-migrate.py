# -*- coding: utf-8 -*-
"""Pre-migración 19.0.0.44 — N-6 en Enterprise: congelar el tipo de
ausencia de vacaciones.

MEDIDO en la base EE del laboratorio (2026-09-22): con el goce de julio
validado, `-u solse_pe_payroll` moría en
`hr_holidays/models/hr_leave.py:749 _check_date_state` desde
`_compute_duration` (:634), disparado por el flush de
`_update_translations`. `hr_salary_rule_bloque8_data.xml` pasa a declarar
`leave_type_vacaciones_pe` y `work_entry_type_vacaciones_pe` con
`noupdate="1"`, pero cambiar el atributo del XML no toca las filas de
`ir_model_data` ya creadas (trampa 13): el flag se guarda cuando el
registro nace. Sin este script, las bases existentes seguirían
reescribiendo el tipo en cada actualización.

En PRE y no en post: después, los datos de esta misma actualización ya
habrían reescrito el registro y disparado el recálculo.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

REGISTROS = ('leave_type_vacaciones_pe', 'work_entry_type_vacaciones_pe')


def migrate(cr, version):
	if not version:
		return
	cr.execute("""
		UPDATE ir_model_data SET noupdate = true
		 WHERE module = 'solse_pe_payroll'
		   AND name IN %s
		   AND NOT noupdate
		RETURNING name
	""", (REGISTROS,))
	congelados = [fila[0] for fila in cr.fetchall()]

	# Sin esto, el ORM sigue sirviendo el `noupdate` anterior durante la
	# carga de datos de ESTA misma actualización y el registro se reescribe
	# igual (lección de N-5b).
	api.Environment(cr, SUPERUSER_ID, {}).invalidate_all()

	if congelados:
		_logger.warning(
			'N-6 (EE): %s congelado(s) (noupdate). Dejan de reescribirse en '
			'cada actualización, que es lo que disparaba el recálculo de '
			'hr.leave.date_from y tumbaba el -u con vacaciones aprobadas.',
			', '.join(congelados))
	else:
		_logger.info('N-6 (EE): los registros del tipo de ausencia ya '
					 'estaban congelados; nada que hacer.')
