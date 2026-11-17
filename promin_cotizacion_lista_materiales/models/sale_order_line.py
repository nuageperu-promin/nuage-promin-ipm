# -*- coding: utf-8 -*-
from odoo import models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _promin_bom_elegida(self):
        """Lista de materiales (BoM) que se imprime para la línea.

        1.º la versión elegida en la línea (campo «Lista de Materiales», `bom_id`);
        2.º si no hay, la BoM por defecto del producto (menor secuencia; la propia de la
        variante tiene prioridad sobre la de la plantilla).
        Se lee con sudo porque el vendedor puede no tener acceso a Fabricación.
        """
        self.ensure_one()
        producto = self.product_id
        if not producto or self.display_type:
            return self.env['mrp.bom']
        elegida = self.bom_id if 'bom_id' in self._fields else False
        if elegida:
            return elegida.sudo()
        Bom = self.env['mrp.bom'].sudo()
        bom = Bom.search([
            ('active', '=', True),
            ('company_id', 'in', [False, self.company_id.id]),
            '|', ('product_id', '=', producto.id),
            '&', ('product_id', '=', False),
            ('product_tmpl_id', '=', producto.product_tmpl_id.id),
        ], order='sequence, id')
        return bom.filtered(lambda b: b.product_id == producto)[:1] or bom[:1]

    def _promin_bom_componentes(self, bom=None):
        """Componentes (primer nivel) de la BoM elegida: código, descripción, cantidad y unidad.

        La cantidad ya está multiplicada por la cantidad cotizada.
        """
        self.ensure_one()
        bom = bom or self._promin_bom_elegida()
        if not bom:
            return []
        producto = self.product_id
        cantidad_bom = self.product_uom_id._compute_quantity(self.product_uom_qty, bom.product_uom_id)
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
