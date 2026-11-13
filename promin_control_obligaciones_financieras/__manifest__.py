# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
{
    'name': 'PROMIN - Control de obligaciones financieras',
    'version': '19.0.1.0.1',
    'category': 'Accounting/Accounting',
    'summary': 'Pagarés, cartas fianza y otras obligaciones: cronograma, alertas, reportes y asientos',
    'description': """
Control de obligaciones financieras (Anexo B, 14.1).

* Registro de pagarés, cartas fianza, leasing, descuento de facturas y otras obligaciones.
* Cronograma de cuotas (capital, interés, comisión, ITF/portes) con carga desde el texto del banco.
* Líneas de crédito con utilizado y disponible (incluye líneas múltiples).
* Alertas automáticas de vencimiento al responsable.
* Reportes: calendario de vencimientos, saldo por banco, intereses y comisiones por mes,
  saldo corriente / no corriente.
* Asientos: desembolso, pago de cuota y ajuste mensual por diferencia de cambio por documento.
* Flujo con roles: Tesorería, Jefe de Finanzas (aprueba), Contabilidad y Consulta.
""",
    'author': 'NUAGE PERU SAC',
    'website': 'https://www.nuage.pe',
    'license': 'LGPL-3',
    'depends': ['account', 'mail'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'security/rules.xml',
        'data/sequence.xml',
        'data/cron.xml',
        'views/res_company_views.xml',
        'views/obligacion_linea_views.xml',
        'views/obligacion_views.xml',
        'views/cuota_views.xml',
        'wizard/pago_wizard_views.xml',
        'wizard/importar_wizard_views.xml',
        'wizard/ajuste_dc_wizard_views.xml',
        'views/menu.xml',
    ],
    'application': True,
    'installable': True,
}
