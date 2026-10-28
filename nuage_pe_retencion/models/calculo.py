# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
"""Cálculo puro de la retención del IGV, sin dependencias de Odoo.

Se mantiene aparte para poder probarlo con casos reales (por ejemplo el
comprobante RT08-00002878 de PROMIN) sin levantar una base de datos.
"""
from decimal import Decimal, ROUND_HALF_UP

CENTIMO = Decimal('0.01')


def _d(valor):
    return Decimal(str(valor))


def redondear(valor):
    """Redondea a céntimos (mitad hacia arriba) y devuelve float."""
    return float(_d(valor).quantize(CENTIMO, rounding=ROUND_HALF_UP))


def asignar_pago(residuales, monto):
    """Reparte `monto` entre los importes pendientes, en el orden recibido.

    >>> asignar_pago([500, 300], 600)
    [500.0, 100.0]
    """
    restante = _d(monto)
    asignado = []
    for residual in residuales:
        if restante > 0:
            parte = min(_d(residual), restante)
        else:
            parte = Decimal('0')
        asignado.append(redondear(parte))
        restante -= parte
    return asignado


def retenido_en_soles(importe, tc, tasa):
    """IGV retenido en S/ de un importe pagado en otra moneda (tc = soles por unidad)."""
    return redondear(_d(importe) * _d(tc) * _d(tasa) / Decimal('100'))


def calcular_retencion(asignaciones, tasa, umbral, tc=1.0):
    """Calcula la retención de una operación de pago.

    `asignaciones`: lista de (clave, importe_pagado, retenible).
    La retención solo procede si la suma de los importes retenibles SUPERA
    el umbral (estrictamente mayor). El umbral está en soles: los importes en
    otra moneda se convierten con `tc` (soles por unidad de la moneda del pago).
    Si procede, se retiene `tasa`% a cada importe retenible, redondeado a
    céntimos por comprobante y expresado en la moneda del pago.

    Devuelve ({clave: retenido}, total_retenido).
    """
    base = sum((_d(imp) for _clave, imp, retenible in asignaciones if retenible),
               Decimal('0'))
    if base * _d(tc) <= _d(umbral):
        return {}, 0.0
    factor = _d(tasa) / Decimal('100')
    resultado = {}
    total = Decimal('0')
    for clave, importe, retenible in asignaciones:
        if not retenible:
            continue
        retenido = (_d(importe) * factor).quantize(CENTIMO, rounding=ROUND_HALF_UP)
        if retenido > 0:
            resultado[clave] = float(retenido)
            total += retenido
    return resultado, float(total)
