{
    'name': 'Nuage - Tipo de cambio: consulta de fechas faltantes',
    'summary': 'Consulta en línea el tipo de cambio SUNAT de fechas sin registro (comprobantes, botón Actualizar T.C.)',
    'description': 'Complementa solse_pe_rate_api: al cambiar la fecha o la moneda de un comprobante en USD, y al confirmarlo, '
                   'consulta el T.C. de esa fecha; si cae en fin de semana o no hay dato usa el último día hábil anterior '
                   '(hasta 7 días) sin crear filas falsas. Recalcula los borradores cuando entra una tasa nueva y el botón '
                   'Actualizar T.C. rellena los días hábiles faltantes de los últimos 30 días.',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Localizations',
    'author': 'NUAGE PERU SAC',
    'website': 'https://nuage.pe',
    'license': 'LGPL-3',
    'depends': ['account', 'solse_pe_rate_api'],
    'installable': True,
    'application': False,
}
