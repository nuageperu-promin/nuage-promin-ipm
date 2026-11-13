# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from ..models.obligacion import G_CONTABILIDAD


class PagoWizard(models.TransientModel):
    _name = 'promin.obligacion.pago.wizard'
    _description = 'Registrar pago de cuota'

    cuota_id = fields.Many2one('promin.obligacion.cuota', string='Cuota', required=True, readonly=True)
    obligacion_id = fields.Many2one(related='cuota_id.obligacion_id', string='Obligación')
    currency_id = fields.Many2one(related='cuota_id.currency_id', string='Moneda')
    fecha_pago = fields.Date(string='Fecha de pago', required=True)
    capital = fields.Monetary(string='Capital', currency_field='currency_id')
    interes = fields.Monetary(string='Interés', currency_field='currency_id')
    comision = fields.Monetary(string='Comisión', currency_field='currency_id')
    itf = fields.Monetary(string='ITF / portes / otros', currency_field='currency_id')
    total = fields.Monetary(string='Total a pagar', currency_field='currency_id', compute='_compute_total')

    @api.depends('capital', 'interes', 'comision', 'itf')
    def _compute_total(self):
        for rec in self:
            rec.total = rec.capital + rec.interes + rec.comision + rec.itf

    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        cuota = self.env['promin.obligacion.cuota'].browse(self.env.context.get('default_cuota_id'))
        if cuota:
            res.update(fecha_pago=cuota.fecha, capital=cuota.capital, interes=cuota.interes,
                       comision=cuota.comision, itf=cuota.itf)
        return res

    def action_confirmar(self):
        self.ensure_one()
        if not self.env.user.has_group(G_CONTABILIDAD) and not self.env.is_superuser():
            raise AccessError(_('Solo Contabilidad puede registrar el pago de una cuota.'))
        cuota = self.cuota_id
        obl = cuota.obligacion_id
        company = obl.company_id
        if obl.state != 'vigente':
            raise UserError(_('La obligación debe estar vigente para registrar pagos.'))
        if cuota.estado == 'pagada':
            raise UserError(_('La cuota ya fue pagada.'))
        obl._validar_contabilidad()
        if self.interes and not company.promin_obl_cta_interes_id:
            raise UserError(_('Configure la cuenta de intereses en la compañía.'))
        if self.comision and not company.promin_obl_cta_comision_id:
            raise UserError(_('Configure la cuenta de comisiones en la compañía.'))
        if self.itf and not company.promin_obl_cta_itf_id:
            raise UserError(_('Configure la cuenta de ITF / portes en la compañía.'))
        glosa = _('Pago cuota %(n)s %(op)s') % {'n': cuota.numero, 'op': obl.nro_operacion}
        total = self.capital + self.interes + self.comision + self.itf
        items = [
            (obl.cuenta_pasivo_id, self.capital, glosa, obl.banco_id),
            (company.promin_obl_cta_interes_id, self.interes, glosa, obl.banco_id),
            (company.promin_obl_cta_comision_id, self.comision, glosa, obl.banco_id),
            (company.promin_obl_cta_itf_id, self.itf, glosa, obl.banco_id),
            (obl.diario_banco_id.default_account_id, -total, glosa, False),
        ]
        move = obl._crear_asiento(self.fecha_pago, items, ref=glosa, cuota=cuota)
        cuota.write({
            'estado': 'pagada', 'fecha_pago': self.fecha_pago, 'move_id': move.id,
            'capital_pagado': self.capital, 'interes_pagado': self.interes,
            'comision_pagada': self.comision, 'itf_pagado': self.itf,
        })
        obl.message_post(body=_('Cuota %(n)s pagada el %(f)s por %(t).2f %(m)s.',
                                n=cuota.numero, f=self.fecha_pago, t=total, m=obl.currency_id.name))
        if obl.tipo != 'carta_fianza' and all(c.estado == 'pagada' for c in obl.cuota_ids):
            obl.state = 'cancelado'
            obl.message_post(body=_('Todas las cuotas pagadas: obligación cancelada.'))
        return {'type': 'ir.actions.act_window_close'}
