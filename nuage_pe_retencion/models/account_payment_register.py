# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .calculo import asignar_pago, calcular_retencion, retenido_en_soles


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    nuage_aplica_retencion = fields.Boolean(compute='_compute_nuage_retencion')
    nuage_aviso_retencion = fields.Char(compute='_compute_nuage_retencion')

    # ------------------------------------------------------------------
    # Reglas
    # ------------------------------------------------------------------
    def _nuage_activo(self):
        """¿Este pago debe evaluar la retención al pagar?"""
        self.ensure_one()
        company = self.company_id
        return bool(
            company.nuage_retener_al_pagar
            and company.agente_retencion
            and self.tipo == 'normal'
            and not self.autodetraccion
            and self.payment_type == 'outbound'
        )

    def _nuage_es_retenible(self, move):
        """Una factura de proveedor es retenible si no está exenta.

        Exentas (SUNAT): detracción, factura ya retenida, boletas/otros
        documentos que no sean factura, operaciones sin IGV, proveedores buenos
        contribuyentes o agentes de retención, y proveedores sin RUC.
        """
        partner = move.partner_id
        return bool(
            move.move_type == 'in_invoice'
            and move.state == 'posted'
            and not move.tiene_detraccion
            and not move.tiene_retencion
            and move.currency_id == self.currency_id
            and move.amount_tax > 0
            and move.l10n_latam_document_type_id.code == '01'
            and partner
            and partner.doc_type == '6'
            and not partner.buen_contribuyente
            and not partner.es_agente_retencion
        )

    def _nuage_tipo_cambio(self):
        """Soles por unidad de la moneda del pago, a la fecha de pago (tabla de tipos de cambio)."""
        self.ensure_one()
        company = self.company_id
        if self.currency_id == company.currency_id:
            return 1.0
        return self.currency_id._get_conversion_rate(
            self.currency_id, company.currency_id, company, self.payment_date)

    def _nuage_calcular_retencion(self, lines, monto):
        """Calcula la retención de UNA operación de pago (un proveedor).

        `lines`: apuntes por pagar que cancela el pago; `monto`: importe del
        pago incluida la retención. Devuelve {'total': x, 'detalle': [...]}.
        """
        self.ensure_one()
        company = self.company_id
        ordenadas = lines.sorted(key=lambda l: (l.date_maturity or fields.Date.today(), l.id))
        asignado = asignar_pago([abs(l.amount_residual) for l in ordenadas], monto)
        por_factura = {}
        for linea, importe in zip(ordenadas, asignado):
            if importe > 0:
                por_factura[linea.move_id] = por_factura.get(linea.move_id, 0.0) + importe
        asignaciones = [
            (move.id, importe, self._nuage_es_retenible(move))
            for move, importe in por_factura.items()
        ]
        tc = self._nuage_tipo_cambio()
        retenidos, total = calcular_retencion(
            asignaciones, company.nuage_ret_tasa, company.nuage_ret_umbral, tc)
        detalle = [
            {'move_id': move.id, 'base': importe, 'retenido': retenidos[move.id],
             'tc': tc,
             'retenido_pen': retenido_en_soles(importe, tc, company.nuage_ret_tasa)}
            for move, importe in por_factura.items() if move.id in retenidos
        ]
        total_pen = round(sum(item['retenido_pen'] for item in detalle), 2)
        return {'total': total, 'total_pen': total_pen, 'detalle': detalle}

    def _nuage_aplicar_retencion(self, vals, lines, monto):
        """Paga el neto y registra la retención contra la cuenta de IGV retenido.

        Se usa el mismo mecanismo que Solse emplea para las diferencias de
        detracción: una línea `write_off_line_vals` en el asiento del pago.
        En un pago saliente el saldo de la línea es negativo (crédito).
        """
        if not self._nuage_activo():
            return vals
        calculo = self._nuage_calcular_retencion(lines, monto)
        retenido = calculo['total']
        if not retenido:
            return vals
        company = self.company_id
        if not company.nuage_ret_cuenta_id:
            raise UserError(_(
                'Configure la cuenta de IGV retenido por pagar en la compañía '
                '(pestaña «Retenciones»).'))
        vals = dict(vals)
        vals['amount'] = vals['amount'] - retenido
        vals['write_off_line_vals'] = list(vals.get('write_off_line_vals') or []) + [{
            'name': _('Retención IGV %s%%') % company.nuage_ret_tasa,
            'account_id': company.nuage_ret_cuenta_id.id,
            'partner_id': vals.get('partner_id'),
            'currency_id': vals.get('currency_id'),
            'amount_currency': -retenido,
            'balance': -calculo['total_pen'],
        }]
        vals['nuage_retencion_monto'] = retenido
        vals['nuage_retencion_data'] = calculo['detalle']
        return vals

    # ------------------------------------------------------------------
    # Aviso en el asistente
    # ------------------------------------------------------------------
    @api.depends(
        'line_ids', 'amount', 'tipo', 'autodetraccion', 'payment_type', 'currency_id',
        'group_payment', 'can_edit_wizard', 'company_id')
    def _compute_nuage_retencion(self):
        for wizard in self:
            wizard.nuage_aplica_retencion = False
            wizard.nuage_aviso_retencion = False
            if not wizard.line_ids or not wizard._nuage_activo():
                continue
            if wizard.can_edit_wizard:
                grupos = [(wizard.line_ids, wizard.amount)]
            elif wizard.group_payment:
                grupos = [(wizard.line_ids.filtered(lambda l, p=p: l.partner_id == p), None)
                          for p in wizard.line_ids.mapped('partner_id')]
            else:
                grupos = [(linea, None) for linea in wizard.line_ids]
            total = 0.0
            for lineas, monto in grupos:
                if monto is None:
                    monto = sum(abs(l.amount_residual) for l in lineas)
                total += wizard._nuage_calcular_retencion(lineas, monto)['total']
            if total:
                wizard.nuage_aplica_retencion = True
                wizard.nuage_aviso_retencion = _(
                    'Se retendrá IGV por %(simbolo)s %(monto).2f (se registra en soles al tipo de cambio de la fecha de pago). El pago a proveedores será por el '
                    'neto y se generará el comprobante de retención.',
                    simbolo=wizard.currency_id.symbol, monto=total)

    # ------------------------------------------------------------------
    # Creación de pagos
    # ------------------------------------------------------------------
    def _create_payment_vals_from_wizard(self, batch_result):
        vals = super()._create_payment_vals_from_wizard(batch_result)
        return self._nuage_aplicar_retencion(vals, batch_result['lines'], vals['amount'])

    def _create_payment_vals_from_batch(self, batch_result):
        vals = super()._create_payment_vals_from_batch(batch_result)
        return self._nuage_aplicar_retencion(vals, batch_result['lines'], vals['amount'])

    def _create_payments(self):
        payments = super()._create_payments()
        if payments:
            payments.filtered(
                lambda p: p.nuage_retencion_data and not p.nuage_retencion_id
            )._nuage_generar_comprobante()
        return payments
