# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
from odoo import api, models
from odoo.tools.image import image_data_uri

from .factura_datos import preparar_datos, tipo_comprobante

CAMPOS_RESPUESTA = ('response', 'sunat_response', 'response_description', 'observacion', 'mensaje')


class ReportFactura(models.AbstractModel):
    _name = 'report.nuage_pe_factura_pdf.report_factura_document'
    _description = 'Reporte de factura (formato PROMIN)'

    def _observacion_sunat(self, move):
        cpe = getattr(move, 'pe_cpe_id', False)
        if not cpe:
            return ''
        for campo in CAMPOS_RESPUESTA:
            valor = getattr(cpe, campo, None)
            if valor and isinstance(valor, str):
                return valor
        return ''

    def _tipo_nota(self, move, tipo):
        campo = 'l10n_pe_edi_refund_reason' if tipo == 'nc' else 'l10n_pe_edi_charge_reason'
        if campo not in move._fields or not move[campo]:
            return ''
        sel = dict(move._fields[campo]._description_selection(self.env))
        return sel.get(move[campo], '')

    def _doc_origen(self, move):
        numero = getattr(move, 'origin_doc_number', '') or ''
        if numero:
            return numero
        origen = getattr(move, 'reversed_entry_id', False) or getattr(move, 'debit_origin_id', False)
        if origen:
            return origen.l10n_latam_document_number or origen.name or ''
        return ''

    def _guia(self, move):
        """Solo el número de la guía de remisión; si no hay, vacío (no el número de entrega)."""
        if 'guide_number' not in move._fields:
            return ''
        return move.guide_number or ''

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['account.move'].browse(docids)
        datos = {}
        for move in docs:
            cuotas = []
            if getattr(move, 'tipo_transaccion', '') == 'credito':
                cuotas = move.obtener_cuotas_pago() or []
            tipo = tipo_comprobante(move)
            valores = preparar_datos(
                move, cuotas=cuotas, guia=self._guia(move),
                observacion_sunat=self._observacion_sunat(move),
                tipo_nota=self._tipo_nota(move, tipo) if tipo != 'factura' else '',
                doc_origen=self._doc_origen(move) if tipo != 'factura' else '')
            logo = move.company_id.logo
            valores['logo'] = image_data_uri(logo) if logo else False
            qr = move.sunat_qr_code if move.is_cpe else False
            valores['qr'] = image_data_uri(qr) if qr else False
            datos[move.id] = valores
        return {'doc_ids': docids, 'doc_model': 'account.move', 'docs': docs, 'datos': datos}
