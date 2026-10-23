# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
{
    'name': 'Órdenes de compra (PROMIN)',
    'summary': 'Formato PDF de orden de compra local e importación, con numeración PMS/PMI',
    'description': """
Órdenes de compra con el formato de PROMIN
==========================================
* Tipo de OC: Local (PMS-0000000) o Importación (PMI-0000000).
* Reporte PDF con el diseño de PROMIN para cada tipo.
* Notas y leyendas fijas editables por compañía.
""",
    'version': '19.0.1.0.0',
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
