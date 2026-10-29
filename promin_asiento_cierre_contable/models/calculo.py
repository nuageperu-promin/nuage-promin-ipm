"""Funciones puras (sin Odoo) del cierre contable."""


def destino_resultado(total_gestion, tolerancia=0.005):
    """total_gestion: suma de saldos (debe - haber) de las cuentas de gestion.
    Negativo = saldo acreedor = utilidad. Devuelve 'utilidad', 'perdida' o None."""
    if abs(total_gestion) < tolerancia:
        return None
    return 'utilidad' if total_gestion < 0 else 'perdida'


def invertir(lineas):
    """Invierte signo de balance e importe en moneda de cada linea."""
    return [dict(l, balance=-l['balance'], amount_currency=-l['amount_currency'])
            for l in lineas]


def esta_cuadrado(lineas, tolerancia=0.005):
    return abs(sum(l['balance'] for l in lineas)) < tolerancia
