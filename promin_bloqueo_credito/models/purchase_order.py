# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

CAMPOS_GRABAR = {'partner_id', 'order_line', 'state', 'currency_id', 'payment_term_id'}
ESTADOS_ABIERTOS = ('draft', 'sent', 'to approve')


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    promin_compra_aviso = fields.Char(
        'Aviso límite de crédito compras', compute='_compute_promin_compra_credito')
    promin_compra_bloqueada = fields.Boolean(
        'Compra bloqueada por crédito', compute='_compute_promin_compra_credito')

    @api.depends('partner_id', 'amount_total', 'currency_id', 'state', 'order_line.price_total',
                 'partner_id.promin_bloquear_compra', 'partner_id.promin_limite_compras',
                 'partner_id.promin_usa_limite_compras')
    def _compute_promin_compra_credito(self):
        for order in self:
            aviso = order._promin_aviso_limite()
            order.promin_compra_aviso = aviso
            order.promin_compra_bloqueada = bool(
                aviso and order.partner_id.commercial_partner_id.promin_bloquear_compra)

    def _promin_aviso_limite(self):
        """Texto del aviso si el proveedor superaría su límite de compras; '' si no aplica."""
        self.ensure_one()
        if self.state not in ESTADOS_ABIERTOS or not self.partner_id:
            return ''
        proveedor = self.partner_id.commercial_partner_id
        company = self.company_id or self.env.company
        proveedor_c = proveedor.with_company(company)
        if not proveedor_c.promin_usa_limite_compras:
            return ''
        limite = proveedor_c.promin_limite_compras
        deuda = self._promin_deuda_proveedor(proveedor, company)
        sin_facturar = self._promin_ordenes_sin_facturar(proveedor, company)
        actual = self.currency_id._convert(
            self.amount_total, company.currency_id, company,
            self.date_order or fields.Date.context_today(self))
        total = deuda + sin_facturar + actual
        if total <= limite:
            return ''
        moneda = company.currency_id.symbol or company.currency_id.name
        return _(
            '%(prov)s superaría su límite de crédito de compras (%(mon)s %(limite)s): deuda '
            'pendiente %(deuda)s + órdenes sin facturar %(sinf)s + esta orden %(actual)s = %(total)s.',
            prov=proveedor.display_name, mon=moneda, limite='{:,.2f}'.format(limite),
            deuda='{:,.2f}'.format(deuda), sinf='{:,.2f}'.format(sin_facturar),
            actual='{:,.2f}'.format(actual), total='{:,.2f}'.format(total))

    def _promin_deuda_proveedor(self, proveedor, company):
        """Saldo pendiente de pago al proveedor (cuentas por pagar publicadas), en moneda de la compañía."""
        grupos = self.env['account.move.line'].sudo()._read_group(
            [('partner_id', 'child_of', proveedor.id), ('company_id', '=', company.id),
             ('parent_state', '=', 'posted'), ('account_id.account_type', '=', 'liability_payable')],
            aggregates=['balance:sum'])
        return -(grupos[0][0] or 0.0) if grupos else 0.0

    def _promin_ordenes_sin_facturar(self, proveedor, company):
        """Órdenes de compra confirmadas, parte aún no facturada, en moneda de la compañía."""
        ordenes = self.env['purchase.order'].sudo().search([
            ('partner_id', 'child_of', proveedor.id), ('company_id', '=', company.id),
            ('state', 'in', ('purchase', 'done')), ('id', '!=', self._origin.id or 0)])
        total = 0.0
        for orden in ordenes:
            importe = 0.0
            for linea in orden.order_line:
                if linea.display_type or not linea.product_qty:
                    continue
                pendiente = linea.product_qty - linea.qty_invoiced
                if pendiente > 0:
                    importe += linea.price_total * pendiente / linea.product_qty
            total += orden.currency_id._convert(
                importe, company.currency_id, company, orden.date_order or fields.Date.today())
        return total

    def _promin_validar_credito(self):
        for order in self:
            if order.state in ESTADOS_ABIERTOS and order.promin_compra_bloqueada:
                raise ValidationError(_(
                    'No se puede grabar la %(doc)s: el proveedor tiene activo el bloqueo de '
                    'cotizaciones y órdenes de compra.\n\n%(aviso)s\n\n'
                    'Reduzca la orden, regularice los pagos o solicite desactivar el bloqueo en el '
                    'contacto del proveedor.', doc=order.name or _('compra'),
                    aviso=order.promin_compra_aviso))

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

    def _promin_rechazar_si_bloqueada(self, accion):
        for order in self:
            if order.promin_compra_bloqueada:
                raise UserError(_(
                    'No se puede %(accion)s %(doc)s: el proveedor superaría su límite de crédito de '
                    'compras y tiene activo el bloqueo.\n\n%(aviso)s',
                    accion=accion, doc=order.name, aviso=order.promin_compra_aviso))

    def button_confirm(self):
        self._promin_rechazar_si_bloqueada(_('confirmar'))
        return super().button_confirm()

    def button_approve(self, force=False):
        self._promin_rechazar_si_bloqueada(_('aprobar'))
        return super().button_approve(force=force)

    def action_rfq_send(self):
        self._promin_rechazar_si_bloqueada(_('enviar'))
        return super().action_rfq_send()

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        """Apaga Enviar, Confirmar y Aprobar cuando la compra está bloqueada."""
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type == 'form' and arch.xpath("//field[@name='promin_compra_bloqueada']"):
            for boton in arch.xpath(
                    "//header/button[@name='button_confirm' or @name='action_rfq_send' "
                    "or @name='button_approve']"):
                actual = boton.get('invisible')
                boton.set('invisible', '(%s) or promin_compra_bloqueada' % actual
                          if actual else 'promin_compra_bloqueada')
        return arch, view
