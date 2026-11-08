from odoo import fields, models
from .common import SECTORES, SECTOR_SQL, factor_sql

QUERY = """
SELECT
    l.id AS id,
    l.move_id AS move_id,
    m.company_id AS company_id,
    p.id AS partner_id,
    m.invoice_user_id AS vendedor_id,
    t.categ_id AS linea_id,
    l.product_id AS product_id,
    m.invoice_date AS fecha,
    m.move_type AS tipo,
    {sector} AS sector,
    COALESCE(p.promin_empresa_relacionada, false) AS es_relacionada,
    l.quantity * CASE WHEN m.move_type = 'out_refund' THEN -1 ELSE 1 END AS cantidad,
    (-l.balance) * k.factor AS facturado_usd
FROM account_move_line l
JOIN account_move m ON m.id = l.move_id
JOIN res_company rc ON rc.id = m.company_id
JOIN res_partner p ON p.id = COALESCE(m.commercial_partner_id, m.partner_id)
LEFT JOIN res_country co ON co.id = p.country_id
LEFT JOIN product_product pp ON pp.id = l.product_id
LEFT JOIN product_template t ON t.id = pp.product_tmpl_id
{factor}
WHERE m.move_type IN ('out_invoice', 'out_refund')
  AND m.state = 'posted'
  AND l.display_type = 'product'
  AND m.invoice_date IS NOT NULL
""".format(sector=SECTOR_SQL, factor=factor_sql('m.invoice_date', 'rc.currency_id', 'm.company_id'))


class ProminTableroFactura(models.Model):
    _name = 'promin.tablero.factura'
    _description = 'Tablero de facturación (USD)'
    _auto = False
    _order = 'fecha desc, id desc'

    move_id = fields.Many2one('account.move', string='Comprobante', readonly=True)
    company_id = fields.Many2one('res.company', string='Compañía', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Cliente', readonly=True)
    vendedor_id = fields.Many2one('res.users', string='Vendedor', readonly=True)
    linea_id = fields.Many2one('product.category', string='Línea', readonly=True)
    product_id = fields.Many2one('product.product', string='Producto', readonly=True)
    fecha = fields.Date(string='Fecha de emisión', readonly=True)
    tipo = fields.Selection([('out_invoice', 'Factura'), ('out_refund', 'Nota de crédito')],
                            string='Tipo', readonly=True)
    sector = fields.Selection(SECTORES, string='Sector', readonly=True)
    es_relacionada = fields.Boolean(string='Empresa relacionada', readonly=True)
    cantidad = fields.Float(string='Cantidad', readonly=True)
    facturado_usd = fields.Float(string='Facturado US$', readonly=True)

    def init(self):
        cr = self.env.cr
        cr.execute("DROP VIEW IF EXISTS %s CASCADE" % self._table)
        cr.execute("CREATE VIEW %s AS (%s)" % (self._table, QUERY))
