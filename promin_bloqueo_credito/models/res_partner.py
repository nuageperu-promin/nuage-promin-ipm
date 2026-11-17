# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    promin_bloquear_venta = fields.Boolean(
        'Bloquear generación de Cotización/Orden de Venta', tracking=True,
        help='Si está activo y el cliente llegó a su límite de crédito, no se podrá grabar ni '
             'continuar una cotización u orden de venta de este cliente. Requiere que el límite '
             'de crédito esté activado en la empresa y en el contacto.')
