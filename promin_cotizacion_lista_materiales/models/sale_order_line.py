# -*- coding: utf-8 -*-
from odoo import models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _promin_bom_componentes(self):
        """Componentes (primer nivel) de la lista de materiales del producto de la línea.

        Devuelve una lista de dicts con código, descripción, cantidad y unidad. La cantidad
        ya está multiplicada por la cantidad cotizada. Sin BoM, devuelve lista vacía.
        Se lee con sudo porque el vendedor puede no tener acceso a Fabricación.
        """
        self.ensure_one()
        producto = self.product_id
        if not producto or self.display_type:
            return []
        Bom = self.env['mrp.bom'].sudo()
        bom = Bom.search([
            ('active', '=', True),
            ('company_id', 'in', [False, self.company_id.id]),
            '|', ('product_id', '=', producto.id),
            '&', ('product_id', '=', False),
            ('product_tmpl_id', '=', producto.product_tmpl_id.id),
        ], order='sequence, id')
        # Primero la BoM propia de la variante; luego la de la plantilla.
        bom = bom.filtered(lambda b: b.product_id == producto)[:1] or bom[:1]
        if not bom:
            return []
        unidad_bom = bom.product_uom_id
        cantidad_bom = self.product_uom_id._compute_quantity(self.product_uom_qty, unidad_bom)
        factor = cantidad_bom / (bom.product_qty or 1.0)
        resultado = []
        for linea in bom.bom_line_ids:
            if linea._skip_bom_line(producto):
                continue
            comp = linea.product_id.with_context(display_default_code=False)
            resultado.append({
                'codigo': linea.product_id.default_code or '',
                'nombre': comp.display_name,
                'cantidad': linea.product_qty * factor,
                'unidad': linea.product_uom_id.name or '',
            })
        return resultado
