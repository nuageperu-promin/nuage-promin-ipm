# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
{
    'name': 'Órdenes de compra (PROMIN)',
    'summary': 'Formato PDF de orden de compra local e importación, con numeración por tipo (PMA, PMC, PMI, PML, PMS, PMT, SRV)',
    'description': """
Órdenes de compra con el formato de PROMIN
==========================================
* Tipo de OC: PMA, PMC, PMI, PML, PMS, PMT, SRV (cada uno con su numeración).
* Dos formatos PDF independientes del tipo: Local e Importación.
* Notas y leyendas fijas editables por compañía.
""",
    'version': '19.0.1.1.1',
    'author': 'NUAGE PERU SAC',
    'license': 'LGPL-3',
    'category': 'Inventory/Purchase',
    'depends': ['purchase'],
    'data': [
        'data/ir_sequence_data.xml',
        'views/res_company_views.xml',
        'views/purchase_order_views.xml',
        'report/oc_report.xml',
    ],
    'installable': True,
    'application': False,
}
