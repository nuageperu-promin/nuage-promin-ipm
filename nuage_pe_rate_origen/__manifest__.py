{
    'name': 'Nuage - Tipo de cambio de NC/ND según comprobante de origen',
    'summary': 'En notas de crédito y débito (ventas y compras) el tipo de cambio sale del comprobante de origen',
    'description': 'En notas de crédito y débito en borrador toma del comprobante de origen la fecha del T.C., el T.C. mostrado, '
                   'el T.C. interno (PLE/SIRE) y la tasa del asiento, en lugar de usar la fecha de la propia nota. '
                   'No modifica notas ya confirmadas.',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Localizations',
    'author': 'NUAGE PERU SAC',
    'website': 'https://nuage.pe',
    'license': 'LGPL-3',
    'depends': ['account', 'solse_pe_accountant', 'solse_pe_rate_api'],
    'installable': True,
    'application': False,
}
