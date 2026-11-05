# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
{
    'name': 'Guías de remisión PDF (PROMIN)',
    'summary': 'Formato PDF de la guía de remisión remitente (transporte privado y público) con el diseño de PROMIN',
    'version': '19.0.1.0.2',
    'author': 'NUAGE PERU SAC',
    'license': 'LGPL-3',
    'category': 'Inventory/Localizations',
    'depends': ['stock', 'solse_pe_cpe_guias'],
    'data': [
        'report/guia_report.xml',
    ],
    'installable': True,
    'application': False,
}
