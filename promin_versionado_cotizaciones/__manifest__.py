{
    'name': 'PROMIN - Versionado de cotizaciones',
    'version': '19.0.1.0.0',
    'summary': 'Cada revisión de una cotización conserva el número con sufijo de versión; solo la última sigue activa',
    'author': 'Nuage Peru SAC',
    'license': 'LGPL-3',
    'category': 'Sales/Sales',
    'depends': ['sale'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/nueva_version_views.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
}
