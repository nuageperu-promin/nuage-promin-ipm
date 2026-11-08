{
    'name': 'PROMIN - Tableros Gerenciales',
    'version': '19.0.0.2.0',
    'category': 'Sales',
    'summary': 'Reportes gerenciales en USD: pedidos, pedidos vs facturación y pendientes por atender',
    'description': """
Prototipo del Módulo de Tableros (Anexo B, 14.4).

* Vista consolidada a nivel de línea de pedido, en USD al tipo de cambio de la fecha del pedido.
* Excluye empresas relacionadas (marca en el cliente) con un filtro activado por defecto.
* Pedidos por línea, sector, vendedor y cliente; pedidos vs facturación; pendientes por atender
  con tramos de 20K y 50K.
""",
    'author': 'NUAGE PERU SAC',
    'website': 'https://www.nuage.pe',
    'license': 'LGPL-3',
    'depends': ['sale', 'sales_team', 'account', 'purchase', 'sale_margin'],
    'data': [
        'security/ir.model.access.csv',
        'security/rules.xml',
        'views/res_partner_views.xml',
        'views/tablero_pedido_views.xml',
        'views/menu.xml',
    ],
    'application': True,
    'installable': True,
}
