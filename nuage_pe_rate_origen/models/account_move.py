from odoo import api, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _nuage_origen_tc(self):
        """Comprobante de origen de una NC/ND (ventas o compras); vacío si no aplica."""
        self.ensure_one()
        if self.move_type in ('out_refund', 'in_refund'):
            return self.reversed_entry_id
        if self.move_type in ('out_invoice', 'in_invoice') and 'debit_origin_id' in self._fields:
            return self.debit_origin_id
        return self.browse()

    @api.depends('move_type', 'date', 'invoice_date', 'es_x_apertura', 'fecha_apertura',
                 'reversed_entry_id.invoice_date', 'reversed_entry_id.date')
    def _compute_fecha_tipo_cambio(self):
        super()._compute_fecha_tipo_cambio()
        for reg in self:
            origen = reg._nuage_origen_tc()
            if origen and (origen.invoice_date or origen.date):
                reg.fecha_tipo_cambio = origen.invoice_date or origen.date

    @api.depends('currency_id', 'company_currency_id', 'company_id', 'invoice_date', 'date',
                 'taxable_supply_date', 'reversed_entry_id')
    def _compute_invoice_currency_rate(self):
        super()._compute_invoice_currency_rate()
        for move in self:
            if move.state != 'draft':
                continue
            origen = move._nuage_origen_tc()
            if origen and origen.currency_id == move.currency_id and origen.invoice_currency_rate:
                move.invoice_currency_rate = origen.invoice_currency_rate

    @api.depends('invoice_date', 'currency_id', 'reversed_entry_id', 'invoice_currency_rate')
    def _compute_tipo_cambio_sistema(self):
        super()._compute_tipo_cambio_sistema()
        for reg in self:
            origen = reg._nuage_origen_tc()
            if origen and origen.currency_id == reg.currency_id:
                reg.tipo_cambio_dolar_sistema = origen.tipo_cambio_dolar_sistema

    def obtener_fecha_tipo_cambio(self):
        origen = self._nuage_origen_tc()
        if origen and (origen.invoice_date or origen.date):
            return origen.invoice_date or origen.date
        return super().obtener_fecha_tipo_cambio()

    @api.depends('currency_id', 'date', 'company_id', 'invoice_date', 'reversed_entry_id')
    def _compute_tipo_cambio(self):
        super()._compute_tipo_cambio()
