# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
{
    'name': 'Nuage - Retenciones del IGV (agente de retención)',
    'summary': 'Retiene el IGV al pagar a proveedores y emite el comprobante de retención',
    'description': """
Retención del IGV al momento del pago a proveedores
===================================================
* La retención se decide al pagar, sumando las facturas del mismo proveedor
  incluidas en la operación de pago.
* Reemplaza (por compañía, con un interruptor) la retención que Solse calcula
  al validar la factura de compra.
* Genera el comprobante de retención (serie y correlativo propios) con su PDF.
* Facturas en dólares: umbral en soles, tipo de cambio de la fecha de pago y retención en S/.
* Reporte por proveedor y mes.
""",
    'version': '19.0.1.1.3',
    'author': 'NUAGE PERU SAC',
    'license': 'LGPL-3',
    'category': 'Accounting/Localizations',
    'depends': ['account', 'solse_pe_edi', 'solse_pe_accountant'],
    'data': [
        'security/ir.model.access.csv',
        'security/nuage_retencion_security.xml',
        'views/res_company_views.xml',
        'views/account_payment_register_views.xml',
        'views/nuage_retencion_views.xml',
        'report/nuage_retencion_report.xml',
    ],
    'installable': True,
    'application': False,
}
