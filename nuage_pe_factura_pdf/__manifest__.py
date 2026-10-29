# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
{
    'name': 'Facturas PDF (PROMIN)',
    'summary': 'Formato PDF de factura y notas de crédito/débito con el diseño de PROMIN',
    'version': '19.0.1.1.1',
    'author': 'NUAGE PERU SAC',
    'license': 'LGPL-3',
    'category': 'Accounting/Localizations',
    'depends': ['account', 'solse_pe_cpe_pdf_ee'],
    'data': [
        'views/res_company_views.xml',
        'report/factura_report.xml',
    ],
    'installable': True,
    'application': False,
}
