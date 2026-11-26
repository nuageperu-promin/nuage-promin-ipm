import logging
from datetime import timedelta
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)
MAX_ATRAS = 7


class ResCurrency(models.Model):
    _inherit = 'res.currency'

    @api.model
    def _nuage_usd_venta(self):
        return self.sudo().search([('name', '=', 'USD'), ('rate_type', '=', 'venta')], limit=1)

    @api.model
    def _nuage_existe_tc(self, fecha, company):
        usd = self._nuage_usd_venta()
        return bool(usd) and bool(self.env['res.currency.rate'].sudo().search_count([
            ('name', '=', fecha), ('currency_id', '=', usd.id), ('company_id', '=', company.id)]))

    @api.model
    def _nuage_asegurar_tc(self, fecha, company):
        """(estado, fecha_usada). estado: exacta | previa | falta | sin_config."""
        fecha = fields.Date.to_date(fecha)
        if not self._nuage_usd_venta() or not company.token_api:
            return 'sin_config', False
        if self._nuage_existe_tc(fecha, company):
            return 'exacta', fecha
        cur = self.with_company(company)
        for atras in range(MAX_ATRAS + 1):
            dia = fecha - timedelta(days=atras)
            if dia.weekday() >= 5:
                continue
            if atras and self._nuage_existe_tc(dia, company):
                return 'previa', dia
            if not self._nuage_existe_tc(dia, company):
                try:
                    cur.update_exchange_rate(dia)
                except Exception as e:
                    _logger.warning("TC %s: error consultando la API: %s", dia, e)
                    return 'falta', False
                if self._nuage_existe_tc(dia, company):
                    return ('exacta' if atras == 0 else 'previa'), dia
        return 'falta', False

    def auto_update_simple(self):
        super().auto_update_simple()
        company = self.env.company
        hoy = fields.Date.context_today(self)
        Rate = self.env['res.currency.rate'].sudo()
        antes = Rate.search_count([('company_id', '=', company.id)])
        for atras in range(1, 31):
            dia = hoy - timedelta(days=atras)
            if dia.weekday() < 5 and not self._nuage_existe_tc(dia, company):
                self._nuage_asegurar_tc(dia, company)
        nuevas = Rate.search_count([('company_id', '=', company.id)]) - antes
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': _('Tipo de cambio'), 'type': 'success', 'sticky': False,
            'message': _('Actualizado. Filas nuevas creadas en los últimos 30 días: %s', nuevas)}}
