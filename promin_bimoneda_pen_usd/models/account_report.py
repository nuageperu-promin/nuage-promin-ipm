# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
import logging

from odoo import api, fields, models
from odoo.tools import SQL

_logger = logging.getLogger(__name__)

NOMBRE_VISTA = 'account.report.form.nuage.bimoneda'


class AccountReport(models.Model):
    _inherit = 'account.report'

    nuage_bimoneda = fields.Boolean(
        string='Mostrar columna USD (bimoneda)',
        help='Agrega, junto a cada columna del reporte, otra en dólares. Los montos '
             'en dólares son la suma del «Saldo USD» de cada línea contable, fijado '
             'con el tipo de cambio de la fecha del movimiento.')

    def _nuage_bimoneda_activo(self):
        self.ensure_one()
        return bool(self.nuage_bimoneda or self.root_report_id.nuage_bimoneda)

    # ------------------------------------------------------------------
    # Columnas: se agrega un nivel de encabezado PEN / USD (el más interno).
    # ------------------------------------------------------------------
    def _init_options_column_headers(self, options, previous_options):
        super()._init_options_column_headers(options, previous_options)
        activo = self._nuage_bimoneda_activo()
        options['nuage_bimoneda'] = activo
        hay_presupuesto = any(b.get('selected') for b in options.get('budgets', []))
        if activo and not hay_presupuesto:
            moneda_cia = self.env.company.currency_id.name or 'PEN'
            options['column_headers'].append([
                {'name': moneda_cia, 'forced_options': {'nuage_moneda': moneda_cia}},
                {'name': 'USD', 'forced_options': {'nuage_moneda': 'USD'}},
            ])

    # ------------------------------------------------------------------
    # Cálculo: en el grupo USD el motor suma nuage_balance_usd en vez de balance.
    # ------------------------------------------------------------------
    def _compute_formula_batch_with_engine_domain(self, options, *args, **kwargs):
        if options.get('nuage_moneda') == 'USD':
            self = self.with_context(nuage_balance_usd=True)
        return super(AccountReport, self)._compute_formula_batch_with_engine_domain(options, *args, **kwargs)

    def _currency_table_apply_rate(self, value):
        if self.env.context.get('nuage_balance_usd') and value.code == 'account_move_line.balance':
            # Ya está en dólares: no se aplica la tabla de conversión de compañías.
            return SQL('account_move_line.nuage_balance_usd')
        return super()._currency_table_apply_rate(value)

    # ------------------------------------------------------------------
    # Preparación (se ejecuta en cada instalación/actualización del módulo).
    # ------------------------------------------------------------------
    @api.model
    def _nuage_bimoneda_setup(self):
        """Activa la columna USD en Balance General y Estado de Resultados y
        muestra el check en el formulario del reporte."""
        reportes = self.with_context(lang='en_US').search([
            '|', ('name', 'ilike', 'Balance Sheet'), ('name', 'ilike', 'Profit and Loss')])
        reportes.write({'nuage_bimoneda': True})

        Vista = self.env['ir.ui.view']
        if Vista.search_count([('name', '=', NOMBRE_VISTA)]):
            return
        try:
            with self.env.cr.savepoint():
                base = Vista.search([('model', '=', 'account.report'), ('type', '=', 'form'),
                                     ('inherit_id', '=', False)], limit=1)
                if base:
                    Vista.create({
                        'name': NOMBRE_VISTA,
                        'model': 'account.report',
                        'inherit_id': base.id,
                        'arch': '<data><xpath expr="//field[@name=\'name\']" position="after">'
                                '<field name="nuage_bimoneda"/></xpath></data>',
                    })
        except Exception:  # la vista es solo una comodidad
            _logger.warning('No se pudo agregar el check bimoneda al formulario del reporte', exc_info=True)
