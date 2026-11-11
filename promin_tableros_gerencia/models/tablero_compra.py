from odoo import fields, models
from .common import factor_sql

QUERY = """
SELECT s.*,
       GREATEST(s.recibido_usd - s.facturado_usd, 0) AS recibido_sin_factura_usd,
       GREATEST(s.facturado_usd - s.recibido_usd, 0) AS facturado_sin_ingreso_usd,
       GREATEST(s.facturado_usd - s.pagado_usd, 0) AS facturado_sin_pago_usd
FROM (
    SELECT
        pl.id AS id,
        pl.order_id AS order_id,
        po.company_id AS company_id,
        po.partner_id AS partner_id,
        po.user_id AS comprador_id,
        t.categ_id AS linea_id,
        pl.product_id AS product_id,
        po.date_order::date AS fecha,
        pl.date_planned::date AS fecha_planificada,
        po.state AS state,
        pl.product_qty AS cantidad,
        pl.qty_received AS cantidad_recibida,
        pl.qty_invoiced AS cantidad_facturada,
        pl.price_subtotal * k.factor AS compra_usd,
        CASE WHEN pl.product_qty > 0
             THEN pl.price_subtotal * pl.qty_received / pl.product_qty
             ELSE 0 END * k.factor AS recibido_usd,
        COALESCE(inv.valor, 0) * k.factor AS facturado_usd,
        COALESCE(inv.pagado, 0) * k.factor AS pagado_usd
    FROM purchase_order_line pl
    JOIN purchase_order po ON po.id = pl.order_id
    LEFT JOIN product_product pp ON pp.id = pl.product_id
    LEFT JOIN product_template t ON t.id = pp.product_tmpl_id
    {factor}
    LEFT JOIN LATERAL (
        SELECT
            SUM(CASE WHEN am.move_type = 'in_refund' THEN -1 ELSE 1 END * aml.price_subtotal) AS valor,
            SUM(CASE WHEN am.payment_state IN ('paid', 'in_payment')
                     THEN CASE WHEN am.move_type = 'in_refund' THEN -1 ELSE 1 END * aml.price_subtotal
                     ELSE 0 END) AS pagado
        FROM account_move_line aml
        JOIN account_move am ON am.id = aml.move_id
        WHERE aml.purchase_line_id = pl.id
          AND am.state = 'posted'
          AND am.move_type IN ('in_invoice', 'in_refund')
    ) inv ON true
    WHERE po.state IN ('purchase', 'done') AND pl.display_type IS NULL
) s
""".format(factor=factor_sql('po.date_order::date', 'po.currency_id', 'po.company_id'))


class ProminTableroCompra(models.Model):
    _name = 'promin.tablero.compra'
    _description = 'Control de compras: ingreso vs factura vs pago (USD)'
    _auto = False
    _order = 'fecha desc, id desc'

    order_id = fields.Many2one('purchase.order', string='Orden de compra', readonly=True)
    company_id = fields.Many2one('res.company', string='Compañía', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Proveedor', readonly=True)
    comprador_id = fields.Many2one('res.users', string='Comprador', readonly=True)
    linea_id = fields.Many2one('product.category', string='Línea', readonly=True)
    product_id = fields.Many2one('product.product', string='Producto', readonly=True)
    fecha = fields.Date(string='Fecha de la OC', readonly=True)
    fecha_planificada = fields.Date(string='Fecha planificada', readonly=True)
    state = fields.Selection([('purchase', 'Orden de compra'), ('done', 'Bloqueado')],
                             string='Estado', readonly=True)
    cantidad = fields.Float(string='Cantidad', readonly=True)
    cantidad_recibida = fields.Float(string='Cantidad recibida', readonly=True)
    cantidad_facturada = fields.Float(string='Cantidad facturada', readonly=True)
    compra_usd = fields.Float(string='Compra US$', readonly=True)
    recibido_usd = fields.Float(string='Recibido en almacén US$', readonly=True)
    facturado_usd = fields.Float(string='Facturado US$', readonly=True)
    pagado_usd = fields.Float(string='Pagado US$', readonly=True)
    recibido_sin_factura_usd = fields.Float(string='Recibido sin factura US$', readonly=True)
    facturado_sin_ingreso_usd = fields.Float(string='Facturado sin ingreso US$', readonly=True)
    facturado_sin_pago_usd = fields.Float(string='Facturado sin pagar US$', readonly=True)

    def init(self):
        cr = self.env.cr
        cr.execute("DROP VIEW IF EXISTS %s CASCADE" % self._table)
        cr.execute("CREATE VIEW %s AS (%s)" % (self._table, QUERY))

    def action_abrir_documento(self):
        """Abre el documento de origen (pedido, comprobante u orden de compra)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'res_id': self.order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
