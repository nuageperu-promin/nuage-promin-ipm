# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    promin_credito_bloqueado = fields.Boolean(
        'Venta bloqueada por crédito', compute='_compute_promin_credito_bloqueado',
        help='El cliente está marcado para bloquear ventas y llegó a su límite de crédito: no se puede confirmar la orden de venta.')

    @api.depends('partner_id', 'partner_credit_warning', 'state')
    def _compute_promin_credito_bloqueado(self):
        for order in self:
            order.promin_credito_bloqueado = order._promin_esta_bloqueada()

    def _promin_esta_bloqueada(self):
        """True si el cliente tiene el bloqueo activo y Odoo avisa que llegó a su límite de crédito.

        El aviso de Odoo (`partner_credit_warning`) solo existe en cotización/enviada y cuando
        el límite de crédito está activado en la empresa y en el contacto.
        """
        self.ensure_one()
        if self.state not in ('draft', 'sent') or not self.partner_id:
            return False
        cliente = self.partner_id.commercial_partner_id
        return bool(cliente.promin_bloquear_venta and self.partner_credit_warning)

    def action_confirm(self):
        for order in self:
            if order._promin_esta_bloqueada():
                raise UserError(_(
                    'No se puede confirmar %(doc)s como orden de venta: el cliente %(cliente)s llegó a su '
                    'límite de crédito y tiene activo el bloqueo de ventas.\n\n%(aviso)s\n\n'
                    'La cotización puede seguir creándose e imprimiéndose. Regularice la deuda o '
                    'solicite desactivar el bloqueo en el contacto del cliente.',
                    doc=order.name,
                    cliente=order.partner_id.commercial_partner_id.display_name,
                    aviso=order.partner_credit_warning or ''))
        return super().action_confirm()

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        """Apaga el botón Confirmar (cotización → orden de venta) cuando el cliente está bloqueado."""
        arch, view = super()._get_view(view_id, view_type, **options)
        # Solo en vistas que tengan el campo (la vista estándar heredada por este módulo).
        if view_type == 'form' and arch.xpath("//field[@name='promin_credito_bloqueado']"):
            for boton in arch.xpath(
                    "//header/button[@name='action_confirm']"):
                actual = boton.get('invisible')
                boton.set('invisible', '(%s) or promin_credito_bloqueado' % actual
                          if actual else 'promin_credito_bloqueado')
        return arch, view
