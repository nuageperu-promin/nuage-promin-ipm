# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
from odoo import api, models
from odoo.tools.image import image_data_uri

from .oc_datos import preparar_datos


class ReportOrdenCompra(models.AbstractModel):
    _name = 'report.nuage_pe_oc.report_oc_document'
    _description = 'Reporte de orden de compra (formato PROMIN)'
    _formato = 'local'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['purchase.order'].browse(docids)
        datos = {}
        for orden in docs:
            valores = preparar_datos(orden, self._formato)
            logo = orden.company_id.logo
            valores['logo'] = image_data_uri(logo) if logo else False
            datos[orden.id] = valores
        return {
            'doc_ids': docids,
            'doc_model': 'purchase.order',
            'docs': docs,
            'datos': datos,
        }


class ReportOrdenCompraLocal(models.AbstractModel):
    _name = 'report.nuage_pe_oc.report_oc_local'
    _inherit = 'report.nuage_pe_oc.report_oc_document'
    _description = 'Orden de compra local (PROMIN)'
    _formato = 'local'


class ReportOrdenCompraImportacion(models.AbstractModel):
    _name = 'report.nuage_pe_oc.report_oc_importacion'
    _inherit = 'report.nuage_pe_oc.report_oc_document'
    _description = 'Orden de compra importación (PROMIN)'
    _formato = 'importacion'
