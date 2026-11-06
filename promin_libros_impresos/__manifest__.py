# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
{
    'name': 'PROMIN - Libro Diario y Libro Mayor impresos (5.1 y 6.1)',
    'summary': 'Imprime el Libro Diario (Formato 5.1) y el Libro Mayor (Formato 6.1) en PDF, estilo clásico',
    'version': '19.0.1.0.2',
    'author': 'NUAGE PERU SAC',
    'license': 'LGPL-3',
    'category': 'Accounting/Localizations',
    'depends': ['account', 'solse_pe_accountant'],
    'data': [
        'security/ir.model.access.csv',
        'views/account_journal_views.xml',
        'views/libro_impreso_views.xml',
    ],
    'installable': True,
    'application': False,
}
