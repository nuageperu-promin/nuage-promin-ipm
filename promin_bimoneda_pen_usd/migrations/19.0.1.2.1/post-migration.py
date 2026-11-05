# -*- coding: utf-8 -*-
# Recalcula el saldo USD con 6 decimales y sin redondeo por línea.
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Linea = env['account.move.line'].with_context(active_test=False)
    campo = Linea._fields['nuage_balance_usd']
    ids = Linea.search([]).ids
    for i in range(0, len(ids), 5000):
        env.add_to_compute(campo, Linea.browse(ids[i:i + 5000]))
        env.flush_all()
        env.invalidate_all()
