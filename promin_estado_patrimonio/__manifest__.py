# -*- coding: utf-8 -*-
{
    'name': 'PROMIN - Estado de Cambios en el Patrimonio (SOL/USD)',
    'version': '19.0.1.0.1',
    'summary': 'Estado de cambios en el patrimonio neto en soles y en dólares (prototipo)',
    'author': 'Nuage Peru SAC',
    'website': 'https://www.nuage.pe',
    'license': 'OPL-1',
    'category': 'Accounting/Accounting',
    'depends': ['account_reports', 'promin_bimoneda_pen_usd',
                'promin_asiento_cierre_contable'],
    'data': ['data/estado_patrimonio.xml'],
    'installable': True,
    'application': False,
}
