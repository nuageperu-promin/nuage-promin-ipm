# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
{
    'name': 'Libros electrónicos PLE (Nuage)',
    'summary': 'Libro Caja y Bancos (1.1, 1.2) y Libro de Inventarios y Balances (3.1) del PLE de SUNAT',
    'description': """
Libros electrónicos PLE — Nuage
===============================
Complementa a ``solse_pe_ple_pro`` con los libros que ese módulo no trae.

Estructuras incluidas
---------------------
* 1.1 (010100) Libro Caja y Bancos — detalle de los movimientos del efectivo.
* 1.2 (010200) Libro Caja y Bancos — detalle de los movimientos de la cuenta
  corriente.
* 3.1 (030100) Libro de Inventarios y Balances — estado de situación
  financiera, por rubro de la Tabla 34, al 31 de diciembre.

Los archivos (TXT y Excel) se generan desde Libros electrónicos (PLE). En el
Libro 1 el CUO y el correlativo son los mismos del Libro Diario y del Libro
Mayor, como exige SUNAT.
""",
    'version': '19.0.1.1.0',
    'author': 'NUAGE PERU SAC',
    'license': 'LGPL-3',
    'category': 'Accounting/Localizations',
    'depends': ['solse_pe_ple_pro', 'solse_pe_accountant'],
    'data': [
        'security/ir.model.access.csv',
        'security/ple_security.xml',
        'views/ple_report_01_views.xml',
        'views/ple_report_03_views.xml',
    ],
    'installable': True,
    'application': False,
}
