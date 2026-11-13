{
    'name': 'PROMIN - Lista de materiales en la cotización',
    'version': '19.0.1.0.0',
    'summary': 'Check en la cotización para imprimir, bajo cada producto, su lista de materiales (BoM)',
    'author': 'Nuage Peru SAC',
    'license': 'LGPL-3',
    'category': 'Sales/Sales',
    'depends': ['sale', 'mrp'],
    'data': [
        'views/sale_order_views.xml',
        'report/report_saleorder.xml',
    ],
    'installable': True,
    'application': False,
}
