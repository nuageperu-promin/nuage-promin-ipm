{
    'name': 'PROMIN - Formato de cotización',
    'version': '19.0.1.0.1',
    'summary': 'Reporte «Cotización PROMIN» con el modelo de Proveedores Mineros (logo, tabla, condiciones y datos bancarios)',
    'author': 'Nuage Peru SAC',
    'license': 'LGPL-3',
    'category': 'Sales/Sales',
    'depends': ['sale', 'promin_cotizacion_lista_materiales'],
    'data': [
        'views/sale_order_views.xml',
        'report/report_cotizacion_promin.xml',
    ],
    'installable': True,
    'application': False,
}
