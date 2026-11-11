# -*- coding: utf-8 -*-
{
    'name': 'PROMIN - Antigüedad de cuentas por cobrar y por pagar (SOL/USD)',
    'version': '19.0.1.0.1',
    'summary': 'Cuenta por cobrar vencida y cuenta por pagar vencida en soles o en dólares',
    'description': """
Agrega la variante en dólares de los reportes «Cuenta por cobrar vencida» y
«Cuenta por pagar vencida», con la misma lógica de los demás reportes bimoneda:
el saldo pendiente en USD usa el tipo de cambio de la fecha de cada movimiento.
El reporte original queda rotulado como (SOL).
    """,
    'author': 'Nuage Peru SAC',
    'website': 'https://www.nuage.pe',
    'license': 'OPL-1',
    'category': 'Accounting/Accounting',
    'depends': ['account_reports', 'promin_bimoneda_pen_usd'],
    'data': ['data/setup.xml'],
    'installable': True,
    'application': False,
}
