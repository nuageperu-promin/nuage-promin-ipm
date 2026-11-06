# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError

from .nombre import nombre_version


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    version_numero = fields.Integer('N.° de versión', default=1, copy=False, readonly=True)
    version_raiz_id = fields.Many2one(
        'sale.order', 'Cotización original', copy=False, readonly=True, index=True,
        help='Primera versión de la cadena de revisiones.')
    version_anterior_id = fields.Many2one(
        'sale.order', 'Versión anterior', copy=False, readonly=True)
    version_reemplazada_por_id = fields.Many2one(
        'sale.order', 'Reemplazada por', copy=False, readonly=True)
    version_historica = fields.Boolean(
        'Es versión anterior', default=False, copy=False, readonly=True, index=True,
        help='Si está marcada, la cotización fue reemplazada por una versión nueva: '
             'queda solo como referencia y no continúa el flujo.')
    version_motivo = fields.Char('Motivo de la revisión', copy=False, readonly=True)
    version_total = fields.Integer('Versiones', compute='_compute_version_total')

    def _compute_version_total(self):
        for orden in self:
            raiz = orden.version_raiz_id or orden
            orden.version_total = self.with_context(active_test=False).search_count(
                ['|', ('id', '=', raiz.id), ('version_raiz_id', '=', raiz.id)])

    # ------------------------------------------------------------------
    def _promin_nueva_version(self, motivo=None):
        """Crea la versión siguiente; la actual queda como referencia (cancelada)."""
        self.ensure_one()
        if self.version_historica:
            raise UserError(_('%s ya fue reemplazada: revise la versión vigente.') % self.name)
        if self.state not in ('draft', 'sent'):
            raise UserError(_(
                '%s ya es un pedido de venta confirmado: solo se versionan cotizaciones.') % self.name)
        raiz = self.version_raiz_id or self
        numero = (self.version_numero or 1) + 1
        nuevo = self.copy({
            'name': nombre_version(raiz.name, numero),
            'version_numero': numero,
            'version_raiz_id': raiz.id,
            'version_anterior_id': self.id,
            'version_motivo': (motivo or '').strip() or False,
        })
        if 'opportunity_id' in self._fields and self.opportunity_id and not nuevo.opportunity_id:
            nuevo.opportunity_id = self.opportunity_id
        self.write({
            'version_raiz_id': raiz.id,
            'version_historica': True,
            'version_reemplazada_por_id': nuevo.id,
        })
        self.with_context(disable_cancel_warning=True).action_cancel()
        self.message_post(body=_('Reemplazada por la versión %s.%s') % (
            nuevo.name, _(' Motivo: %s') % motivo if motivo else ''))
        nuevo.message_post(body=_('Nueva versión creada a partir de %s.%s') % (
            self.name, _(' Motivo: %s') % motivo if motivo else ''))
        return nuevo

    def action_ver_versiones(self):
        self.ensure_one()
        raiz = self.version_raiz_id or self
        return {
            'type': 'ir.actions.act_window',
            'name': _('Versiones de %s') % raiz.name,
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': ['|', ('id', '=', raiz.id), ('version_raiz_id', '=', raiz.id)],
            'context': {'active_test': False, 'create': False},
        }

    def action_abrir_version_vigente(self):
        self.ensure_one()
        vigente = self
        while vigente.version_reemplazada_por_id:
            vigente = vigente.version_reemplazada_por_id
        return {
            'type': 'ir.actions.act_window', 'res_model': 'sale.order',
            'res_id': vigente.id, 'view_mode': 'form', 'target': 'current',
        }

    # Una versión anterior no puede volver al flujo -------------------------
    def action_confirm(self):
        if self.filtered('version_historica'):
            raise UserError(_('Una versión anterior no se puede confirmar: use la versión vigente.'))
        return super().action_confirm()

    def action_draft(self):
        if self.filtered('version_historica'):
            raise UserError(_('Una versión anterior no se puede volver a cotización: use la versión vigente.'))
        return super().action_draft()
