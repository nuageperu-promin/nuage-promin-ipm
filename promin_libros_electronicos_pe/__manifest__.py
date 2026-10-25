# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
{
    'name': 'Libros electrónicos PLE (PROMIN)',
    'summary': 'Libro Caja y Bancos (estructuras 1.1 y 1.2) del PLE de SUNAT',
    'description': """
Libros electrónicos PLE — PROMIN
================================
Complementa a ``solse_pe_ple_pro`` con los libros que ese módulo no trae.

Estructuras incluidas
---------------------
* 1.1 (010100) Libro Caja y Bancos — detalle de los movimientos del efectivo.
* 1.2 (010200) Libro Caja y Bancos — detalle de los movimientos de la cuenta
  corriente.

Los dos archivos (TXT y Excel) se generan por mes desde Libros electrónicos
(PLE) → Estructura 01. El CUO y el correlativo son los mismos del Libro Diario
y del Libro Mayor, como exige SUNAT.
""",
    'version': '19.0.1.0.0',
    'author': 'NUAGE PERU SAC',
    'license': 'LGPL-3',
    'category': 'Accounting/Localizations',
    'depends': ['solse_pe_ple_pro'],
    'data': [
        'security/ir.model.access.csv',
        'security/ple_report_01_security.xml',
        'views/ple_report_01_views.xml',
    ],
    'installable': True,
    'application': False,
}
