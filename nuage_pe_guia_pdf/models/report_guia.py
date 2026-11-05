# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
from odoo import api, fields, models
from odoo.tools.image import image_data_uri

from .guia_datos import preparar_datos, texto_plano


class ReportGuia(models.AbstractModel):
    _name = 'report.nuage_pe_guia_pdf.report_guia_document'
    _description = 'Reporte de guía de remisión remitente (formato PROMIN)'

    def _etiqueta(self, picking, campo):
        if campo not in picking._fields or not picking[campo]:
            return ''
        sel = dict(picking._fields[campo]._description_selection(self.env))
        return sel.get(picking[campo], '')

    def _facturas(self, picking):
        """Documentos relacionados: los cargados en la guía o las facturas de la venta."""
        res = []
        for rel in picking.pe_documento_relacionado_ids:
            sel = dict(rel._fields['codigo_documento']._description_selection(self.env))
            ruc = rel.emisor_id.vat if rel.emisor_id else picking.company_id.vat
            res.append((sel.get(rel.codigo_documento, ''), rel.numero_documento, ruc or ''))
        if not res:
            for inv in picking.pe_invoice_ids:
                res.append(('FACTURA', inv.l10n_latam_document_number or inv.name, picking.company_id.vat or ''))
        return res

    def _orden_compra(self, picking):
        venta = getattr(picking, 'sale_id', False)
        if venta and getattr(venta, 'client_order_ref', False):
            return venta.client_order_ref
        return ''

    def _conductores(self, picking):
        emite = picking._emite_vehiculos_conductores() if picking.pe_transport_mode == '01' else True
        if picking.pe_transport_mode == '01' and not emite:
            return []
        res = []
        for fl in picking.pe_fleet_ids:
            driver = fl.driver_id
            res.append({
                'principal': bool(fl.is_main),
                'placa': fl.name or '',
                'dni': driver.doc_number or driver.vat or '',
                'nombre': driver.name or '',
                'licencia': driver.pe_driver_license or '',
                'tuce': fl.pe_tuce or '',
            })
        return res

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['stock.picking'].browse(docids)
        datos = {}
        for picking in docs:
            etiquetas = {
                'motivo': self._etiqueta(picking, 'pe_transfer_code'),
                'modalidad': self._etiqueta(picking, 'pe_transport_mode'),
            }
            observaciones = texto_plano(picking.note)
            if picking.pe_note:
                observaciones.append(picking.pe_note)
            elif picking.pe_guide_state == 'done' and picking.pe_guide_number not in ('/', False):
                observaciones.append('El Comprobante numero %s, ha sido aceptado' % picking.pe_guide_number)
            valores = preparar_datos(
                picking, etiquetas, orden_compra=self._orden_compra(picking),
                facturas=self._facturas(picking), observaciones=observaciones,
                conductores=self._conductores(picking),
                hoy=fields.Date.context_today(self))
            logo = picking.company_id.logo
            valores['logo'] = image_data_uri(logo) if logo else False
            qr = picking.sunat_qr_code if picking.pe_is_eguide else False
            valores['qr'] = image_data_uri(qr) if qr else False
            datos[picking.id] = valores
        return {'doc_ids': docids, 'doc_model': 'stock.picking', 'docs': docs, 'datos': datos}
