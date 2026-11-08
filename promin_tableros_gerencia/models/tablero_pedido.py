from odoo import fields, models
from .common import SECTORES, SECTOR_SQL, factor_sql

QUERY = """
SELECT
    l.id AS id,
    l.order_id AS order_id,
    o.company_id AS company_id,
    o.partner_id AS partner_id,
    o.user_id AS vendedor_id,
    t.categ_id AS linea_id,
    l.product_id AS product_id,
    o.date_order::date AS fecha,
    to_char(o.date_order, 'YYYY') || '-S' ||
        CASE WHEN extract(month FROM o.date_order) <= 6 THEN '1' ELSE '2' END AS semestre,
    o.commitment_date::date AS fecha_entrega,
    {sector} AS sector,
    o.promin_integrador AS integrador,
    COALESCE(p.promin_empresa_relacionada, false) AS es_relacionada,
    o.state AS state,
    o.invoice_status AS invoice_status,
    l.product_uom_qty AS cantidad,
    l.qty_invoiced AS cantidad_facturada,
    l.qty_delivered AS cantidad_entregada,
    l.price_subtotal * k.factor AS pedido_usd,
    COALESCE(l.purchase_price, 0) * l.product_uom_qty * k.factor AS costo_usd,
    COALESCE(l.margin, 0) * k.factor AS margen_usd,
    CASE WHEN l.product_uom_qty > 0
         THEN l.price_subtotal * LEAST(l.qty_invoiced, l.product_uom_qty) / l.product_uom_qty
         ELSE 0 END * k.factor AS facturado_usd,
    CASE WHEN l.product_uom_qty > 0
         THEN l.price_subtotal * GREATEST(l.product_uom_qty - l.qty_invoiced, 0) / l.product_uom_qty
         ELSE 0 END * k.factor AS pendiente_facturar_usd,
    CASE WHEN l.product_uom_qty > 0
         THEN l.price_subtotal * GREATEST(l.product_uom_qty - l.qty_delivered, 0) / l.product_uom_qty
         ELSE 0 END * k.factor AS pendiente_entrega_usd,
    CASE
        WHEN SUM(l.price_subtotal * k.factor) OVER (PARTITION BY l.order_id) >= 50000 THEN '50k'
        WHEN SUM(l.price_subtotal * k.factor) OVER (PARTITION BY l.order_id) >= 20000 THEN '20k'
        ELSE 'menor'
    END AS tramo
FROM sale_order_line l
JOIN sale_order o ON o.id = l.order_id
JOIN res_partner p ON p.id = o.partner_id
LEFT JOIN res_country co ON co.id = p.country_id
LEFT JOIN product_product pp ON pp.id = l.product_id
LEFT JOIN product_template t ON t.id = pp.product_tmpl_id
{factor}
WHERE o.state IN ('sale', 'done') AND l.display_type IS NULL
""".format(sector=SECTOR_SQL, factor=factor_sql('o.date_order::date', 'o.currency_id', 'o.company_id'))


class ProminTableroPedido(models.Model):
    _name = 'promin.tablero.pedido'
    _description = 'Tablero de pedidos (USD)'
    _auto = False
    _order = 'fecha desc, id desc'

    order_id = fields.Many2one('sale.order', string='Pedido', readonly=True)
    company_id = fields.Many2one('res.company', string='Compañía', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Cliente', readonly=True)
    vendedor_id = fields.Many2one('res.users', string='Vendedor', readonly=True)
    linea_id = fields.Many2one('product.category', string='Línea', readonly=True)
    product_id = fields.Many2one('product.product', string='Producto', readonly=True)
    fecha = fields.Date(string='Fecha del pedido', readonly=True)
    semestre = fields.Char(string='Semestre', readonly=True)
    fecha_entrega = fields.Date(string='Fecha de entrega', readonly=True)
    sector = fields.Selection(SECTORES, string='Sector', readonly=True)
    integrador = fields.Selection([('interno', 'Interno'), ('externo', 'Externo')],
                                  string='Integrador', readonly=True)
    es_relacionada = fields.Boolean(string='Empresa relacionada', readonly=True)
    state = fields.Selection([('sale', 'Pedido de venta'), ('done', 'Bloqueado')],
                             string='Estado', readonly=True)
    invoice_status = fields.Selection(
        [('upselling', 'Oportunidad de venta adicional'), ('invoiced', 'Facturado'),
         ('to invoice', 'Por facturar'), ('no', 'Nada que facturar')],
        string='Estado de facturación', readonly=True)
    tramo = fields.Selection(
        [('50k', 'Pedido de 50K o más'), ('20k', 'Pedido de 20K a 50K'), ('menor', 'Pedido menor a 20K')],
        string='Tramo del pedido', readonly=True)
    cantidad = fields.Float(string='Cantidad', readonly=True)
    cantidad_facturada = fields.Float(string='Cantidad facturada', readonly=True)
    cantidad_entregada = fields.Float(string='Cantidad entregada', readonly=True)
    pedido_usd = fields.Float(string='Pedido US$', readonly=True)
    costo_usd = fields.Float(string='Costo US$', readonly=True)
    margen_usd = fields.Float(string='Margen US$', readonly=True)
    facturado_usd = fields.Float(string='Facturado US$', readonly=True)
    pendiente_facturar_usd = fields.Float(string='Pendiente de facturar US$', readonly=True)
    pendiente_entrega_usd = fields.Float(string='Pendiente de entrega US$', readonly=True)

    def init(self):
        cr = self.env.cr
        cr.execute("DROP VIEW IF EXISTS %s CASCADE" % self._table)
        cr.execute("CREATE VIEW %s AS (%s)" % (self._table, QUERY))
