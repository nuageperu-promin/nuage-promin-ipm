# -*- coding: utf-8 -*-
from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    promin_imprime_bom = fields.Boolean(
        'Se imprime Lista de Materiales', default=False,
        help='Si está marcado, al imprimir la cotización se muestra, debajo de cada producto, '
             'la lista de materiales (BoM) con sus componentes y cantidades. No muestra precios.')
