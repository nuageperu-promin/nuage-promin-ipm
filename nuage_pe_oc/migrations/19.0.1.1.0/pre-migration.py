# -*- coding: utf-8 -*-
def migrate(cr, version):
    """Local pasa a PMS y Importación a PMI; conserva secuencias y contadores."""
    cr.execute("UPDATE purchase_order SET nuage_tipo_oc='pms' WHERE nuage_tipo_oc='local'")
    cr.execute("UPDATE purchase_order SET nuage_tipo_oc='pmi' WHERE nuage_tipo_oc='importacion'")
    for viejo, nuevo, nombre in (('local', 'pms', 'OC Stock (PMS)'),
                                 ('importacion', 'pmi', 'OC Importación (PMI)')):
        cr.execute("UPDATE ir_sequence SET code=%s, name=%s WHERE code=%s",
                   ('nuage.oc.' + nuevo, nombre, 'nuage.oc.' + viejo))
        cr.execute("""UPDATE ir_model_data SET name=%s
                       WHERE module='nuage_pe_oc' AND name=%s""",
                   ('nuage_seq_oc_' + nuevo, 'nuage_seq_oc_' + viejo))
