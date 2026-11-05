# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
from odoo import _, fields, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    nuage_retencion_monto = fields.Monetary(
        'IGV retenido (Nuage)', currency_field='currency_id', copy=False, readonly=True)
    nuage_retencion_data = fields.Json('Detalle de retención (Nuage)', copy=False, readonly=True)
    nuage_retencion_id = fields.Many2one(
        'nuage.retencion', 'Comprobante de retención', copy=False, readonly=True)

    def _nuage_generar_comprobante(self):
        """Crea (en borrador) el comprobante de retención de cada pago con retención."""
        Retencion = self.env['nuage.retencion'].sudo()
        Linea = self.env['nuage.retencion.line'].sudo()
        for pago in self.sudo():
            data = pago.nuage_retencion_data or []
            if pago.nuage_retencion_id or not data:
                continue
            company = pago.company_id
            lineas = []
            for item in data:
                move = self.env['account.move'].sudo().browse(item['move_id'])
                nro_pago = Linea.search_count([
                    ('move_id', '=', move.id), ('state', '!=', 'cancelado')]) + 1
                base = item['base']
                retenido = item['retenido']
                tc = item.get('tc') or 1.0
                retenido_pen = item.get('retenido_pen', retenido)
                lineas.append((0, 0, {
                    'move_id': move.id,
                    'moneda_origen_id': pago.currency_id.id,
                    'fecha_pago': pago.date,
                    'nro_pago': nro_pago,
                    'tipo_cambio': tc,
                    'importe_operacion': move.amount_total,
                    'importe_pago': base,
                    'importe_pago_pen': round(base * tc, 2),
                    'importe_retenido': retenido_pen,
                    'importe_neto': round(base * tc, 2) - retenido_pen,
                }))
            comprobante = Retencion.create({
                'company_id': company.id,
                'partner_id': pago.partner_id.id,
                'date': pago.date,
                'tasa': company.nuage_ret_tasa,
                'payment_id': pago.id,
                'line_ids': lineas,
            })
            pago.nuage_retencion_id = comprobante.id
            pago.message_post(body=_(
                'Se generó el comprobante de retención en borrador (IGV retenido %(monto).2f %(moneda)s). '
                'Emítalo desde Proveedores > Comprobantes de retención.',
                monto=pago.nuage_retencion_monto, moneda=pago.currency_id.name))
        return True
