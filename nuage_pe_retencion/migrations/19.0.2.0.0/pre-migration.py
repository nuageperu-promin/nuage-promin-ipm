# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
"""Los comprobantes de retención ya emitidos antes de la integración con la OSE
quedan como «No enviado»: si no, al activar el envío automático el cron los
enviaría todos de golpe (incluidos los de prueba)."""


def migrate(cr, version):
    cr.execute("SELECT to_regclass('nuage_retencion')")
    if not cr.fetchone()[0]:
        return
    cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'nuage_retencion' AND column_name = 'ose_estado'""")
    if cr.fetchone():
        return
    cr.execute("ALTER TABLE nuage_retencion ADD COLUMN ose_estado varchar")
    cr.execute("UPDATE nuage_retencion SET ose_estado = 'omitido'")
