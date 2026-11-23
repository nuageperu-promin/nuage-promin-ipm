# -*- coding: utf-8 -*-
from odoo import api, fields, models

ETIQUETA_VENTAS = 'Límite de Crédito Ventas'
CAMPOS_LIMITE_VENTAS = ('credit_limit', 'use_partner_credit_limit')


class ResPartner(models.Model):
    _inherit = 'res.partner'

    promin_bloquear_venta = fields.Boolean(
        'Bloquear generación de Cotización/Orden de Venta', tracking=True,
        help='Si está activo y el cliente llegó a su límite de crédito, no se podrá grabar ni '
             'continuar una cotización u orden de venta de este cliente. Requiere que el límite '
             'de crédito esté activado en la empresa y en el contacto.')
    promin_limite_compras = fields.Float(
        'Límite de Crédito Compras', company_dependent=True,
        help='Monto máximo (en la moneda de la compañía) que PROMIN puede deber a este proveedor: '
             'deuda pendiente + órdenes de compra confirmadas sin facturar + la cotización/orden '
             'que se está digitando. Con 0 no se controla.')
    promin_bloquear_compra = fields.Boolean(
        'Bloquear generación de Cotización/Orden de Compra', tracking=True,
        help='Si está activo y el proveedor superaría su límite de crédito de compras, no se podrá '
             'grabar ni continuar una cotización u orden de compra de este proveedor.')

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        """Renombra «Límite de crédito» a «Límite de Crédito Ventas» en el formulario del contacto."""
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type == 'form' and arch.xpath("//field[@name='promin_limite_compras']"):
            for nombre in CAMPOS_LIMITE_VENTAS:
                for nodo in arch.xpath("//field[@name='%s'] | //label[@for='%s']" % (nombre, nombre)):
                    if nodo.tag == 'label' or nombre == 'credit_limit':
                        nodo.set('string', ETIQUETA_VENTAS)
        return arch, view
