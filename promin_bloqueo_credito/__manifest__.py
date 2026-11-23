{
    'name': 'PROMIN - Bloqueo de ventas y compras por límite de crédito',
    'version': '19.0.1.1.0',
    'summary': 'Bloquea cotizaciones/órdenes de venta y de compra al llegar al límite de crédito (clientes y proveedores)',
    'author': 'Nuage Peru SAC',
    'license': 'LGPL-3',
    'category': 'Sales/Sales',
    'depends': ['sale', 'purchase', 'account'],
    'data': [
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
        'views/purchase_order_views.xml',
    ],
    'installable': True,
    'application': False,
}
