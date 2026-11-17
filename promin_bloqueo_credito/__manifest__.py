{
    'name': 'PROMIN - Bloqueo de ventas por límite de crédito',
    'version': '19.0.1.0.0',
    'summary': 'Bloquea cotizaciones y órdenes de venta de clientes que llegaron a su límite de crédito',
    'author': 'Nuage Peru SAC',
    'license': 'LGPL-3',
    'category': 'Sales/Sales',
    'depends': ['sale', 'account'],
    'data': [
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
}
