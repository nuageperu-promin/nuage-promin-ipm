# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# Cambios que cuentan como «grabar» una venta (pasar a cancelada se permite siempre).
CAMPOS_GRABAR = {'partner_id', 'order_line', 'pricelist_id', 'state', 'payment_term_id'}


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    promin_credito_bloqueado = fields.Boolean(
        'Venta bloqueada por crédito', compute='_compute_promin_credito_bloqueado',
        help='El cliente está marcado para bloquear ventas y llegó a su límite de crédito.')

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

    def _promin_validar_credito(self):
        for order in self:
            if order._promin_esta_bloqueada():
                raise ValidationError(_(
                    'No se puede grabar la %(doc)s: el cliente %(cliente)s llegó a su límite de crédito '
                    'y tiene activo el bloqueo de cotizaciones y órdenes de venta.\n\n%(aviso)s\n\n'
                    'Regularice la deuda o solicite desactivar el bloqueo en el contacto del cliente.',
                    doc=order.name or _('venta'),
                    cliente=order.partner_id.commercial_partner_id.display_name,
                    aviso=order.partner_credit_warning or ''))

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        orders._promin_validar_credito()
        return orders

    def write(self, vals):
        res = super().write(vals)
        if vals.get('state') != 'cancel' and CAMPOS_GRABAR & set(vals):
            self._promin_validar_credito()
        return res

    def action_confirm(self):
        for order in self:
            if order._promin_esta_bloqueada():
                raise UserError(_(
                    'No se puede confirmar %(doc)s: el cliente llegó a su límite de crédito y tiene '
                    'activo el bloqueo de ventas.', doc=order.name))
        return super().action_confirm()

    def action_quotation_send(self):
        for order in self:
            if order._promin_esta_bloqueada():
                raise UserError(_(
                    'No se puede enviar %(doc)s: el cliente llegó a su límite de crédito y tiene '
                    'activo el bloqueo de ventas.', doc=order.name))
        return super().action_quotation_send()

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        """Apaga los botones Enviar y Confirmar cuando la venta está bloqueada (todas sus variantes)."""
        arch, view = super()._get_view(view_id, view_type, **options)
        # Solo en vistas que tengan el campo (la vista estándar heredada por este módulo).
        if view_type == 'form' and arch.xpath("//field[@name='promin_credito_bloqueado']"):
            for boton in arch.xpath(
                    "//header/button[@name='action_confirm' or @name='action_quotation_send']"):
                actual = boton.get('invisible')
                boton.set('invisible', '(%s) or promin_credito_bloqueado' % actual
                          if actual else 'promin_credito_bloqueado')
        return arch, view
