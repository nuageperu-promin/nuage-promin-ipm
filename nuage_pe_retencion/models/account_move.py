# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _validar_detraccion_retencion(self, forzar_retencion):
        """Con 'Retener IGV al pagar' activo, la factura de proveedor no lleva
        retención: se calcula al registrar el pago. La detracción se conserva."""
        self.ensure_one()
        datos = super()._validar_detraccion_retencion(forzar_retencion)
        if (self.move_type in ('in_invoice', 'in_refund')
                and self.company_id.nuage_retener_al_pagar):
            datos = dict(
                datos,
                tiene_retencion=False,
                monto_retencion=0.0,
                monto_retencion_base=0.0,
            )
        return datos
