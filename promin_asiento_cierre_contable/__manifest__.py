{
    'name': 'PROMIN - Asiento de cierre y apertura contable',
    'version': '19.0.1.0.1',
    'summary': 'Genera el cierre de resultados, el cierre de balance y la apertura del ejercicio siguiente',
    'author': 'Nuage Peru SAC',
    'license': 'LGPL-3',
    'category': 'Accounting/Accounting',
    'depends': ['account', 'solse_pe_accountant'],
    'data': [
        'security/ir.model.access.csv',
        'views/nuage_cierre_views.xml',
    ],
    'installable': True,
    'application': False,
}
