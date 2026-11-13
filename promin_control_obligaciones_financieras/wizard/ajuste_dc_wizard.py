# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError

from ..models.obligacion import G_CONTABILIDAD


class AjusteDcWizard(models.TransientModel):
    _name = 'promin.obligacion.ajuste.dc.wizard'
    _description = 'Ajuste mensual por diferencia de cambio por documento'

    fecha = fields.Date(string='Fecha de cierre', required=True,
                        default=lambda self: fields.Date.end_of(fields.Date.context_today(self), 'month'))
    company_id = fields.Many2one('res.company', string='Compañía', required=True,
                                 default=lambda self: self.env.company)
    obligacion_ids = fields.Many2many('promin.obligacion', string='Obligaciones',
                                      help='Vacío = todas las obligaciones en moneda extranjera con saldo.')

    def action_ajustar(self):
        self.ensure_one()
        if not self.env.user.has_group(G_CONTABILIDAD) and not self.env.is_superuser():
            raise AccessError(_('Solo Contabilidad puede generar el ajuste por diferencia de cambio.'))
        company = self.company_id
        if not company.promin_obl_cta_dc_ganancia_id or not company.promin_obl_cta_dc_perdida_id:
            raise UserError(_('Configure las cuentas de ganancia y pérdida por diferencia de cambio en la compañía.'))
        ccur = company.currency_id
        dominio = [('company_id', '=', company.id), ('state', 'in', ('vigente', 'cancelado')),
                   ('currency_id', '!=', ccur.id), ('tipo', '!=', 'carta_fianza')]
        obligaciones = self.obligacion_ids or self.env['promin.obligacion'].search(dominio)
        Line = self.env['account.move.line']
        creados = self.env['account.move']
        for obl in obligaciones:
            if not obl.cuenta_pasivo_id or obl.fecha_desembolso > self.fecha:
                continue
            saldo = obl._saldo_a_fecha(self.fecha)
            tasa = self.env['res.currency']._get_conversion_rate(obl.currency_id, ccur, company, self.fecha)
            objetivo = -ccur.round(saldo * tasa)
            lineas = Line.search([
                ('move_id.promin_obligacion_id', '=', obl.id), ('account_id', '=', obl.cuenta_pasivo_id.id),
                ('parent_state', '=', 'posted'), ('date', '<=', self.fecha)])
            actual = sum(lineas.mapped('balance'))
            dif = ccur.round(objetivo - actual)
            if abs(dif) < 0.01:
                continue
            glosa = _('Diferencia de cambio %(op)s al %(f)s') % {'op': obl.nro_operacion, 'f': self.fecha}
            # dif < 0: el pasivo aumenta (pérdida). dif > 0: el pasivo disminuye (ganancia).
            cuenta_dc = (company.promin_obl_cta_dc_perdida_id if dif < 0
                         else company.promin_obl_cta_dc_ganancia_id)
            move = self.env['account.move'].create({
                'move_type': 'entry', 'date': self.fecha, 'ref': glosa, 'company_id': company.id,
                'journal_id': obl._diario_asientos().id, 'promin_obligacion_id': obl.id,
                'line_ids': [
                    (0, 0, {'account_id': obl.cuenta_pasivo_id.id, 'name': glosa, 'balance': dif,
                            'currency_id': obl.currency_id.id, 'amount_currency': 0.0,
                            'partner_id': obl.banco_id.id}),
                    (0, 0, {'account_id': cuenta_dc.id, 'name': glosa, 'balance': -dif}),
                ],
            })
            move.action_post()
            creados |= move
            obl.message_post(body=_('Ajuste por diferencia de cambio al %(f)s: %(d).2f.', f=self.fecha, d=dif))
        if not creados:
            raise UserError(_('No hay diferencias de cambio que ajustar a esa fecha.'))
        return {
            'type': 'ir.actions.act_window', 'name': _('Asientos de diferencia de cambio'),
            'res_model': 'account.move', 'view_mode': 'list,form', 'domain': [('id', 'in', creados.ids)],
        }
