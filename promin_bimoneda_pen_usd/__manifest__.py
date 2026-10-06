# -*- coding: utf-8 -*-
{
    'name': 'Bimoneda PEN/USD - Proveedores Mineros / IPM',
    'version': '19.0.1.0.0',
    'summary': 'Estados financieros, moneda de transacción y valuación de Inventario en bimoneda (PEN/USD).',
    'description': """
Desarrollo a medida para Proveedores Mineros S.A.C. / Industria Proveedores Mineros S.C.R.L.

Incluye:
- Mantenimiento de la moneda de transacción original de cada operación.
- Cálculo de la diferencia de tipo de cambio.
- Valuación de Inventario en bimoneda.
- Generación de estados financieros valorizados en PEN y USD.

Especificación funcional pendiente de aprobación. Este manifest y la estructura
de carpetas son el esqueleto base; los modelos y vistas se completan una vez
aprobada la especificación.
    """,
    'author': 'Nuage Perú S.A.C.',
    'website': 'https://www.nuage.pe',
    'category': 'Accounting/Localizations',
    'license': 'OPL-1',
    'depends': [
        'account',
        'l10n_pe',
    ],
    'data': [
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'application': False,
}
