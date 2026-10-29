# -*- coding: utf-8 -*-
# Vincula los asientos de cierres ya generados con su registro de cierre.
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for cierre in env['nuage.cierre'].search([]):
        (cierre.move_resultados_id | cierre.move_cierre_id | cierre.move_apertura_id).write(
            {'nuage_cierre_id': cierre.id})
