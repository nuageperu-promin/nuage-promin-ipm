# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
"""Formato del Libro 3 (Inventarios y Balances) del PLE de SUNAT.

Funciones puras, sin dependencia de Odoo (se prueban con ``unittest``).

Fuente: «Estructura del PLE» de SUNAT, hoja «3 Libro Inventarios y Balances»
y hoja «Reglas de nombres de libros».

  3.1 (030100) Estado de situación financiera ...... 5 campos:
      C1 periodo AAAAMMDD · C2 catálogo (Tabla 22) · C3 rubro (Tabla 34) ·
      C4 saldo del rubro · C5 estado de la operación.

El estado de situación se arma sumando, por rubro de la Tabla 34, el saldo de
cada cuenta contable a la fecha del balance. Los importes viajan en CÉNTIMOS.
"""

CAMPOS_31 = 5

# Código de oportunidad de presentación (CC del nombre de archivo): al 31/12.
OPORTUNIDAD_CIERRE_ANUAL = '01'

DEUDORA = 'D'      # activos: saldo = debe - haber
ACREEDORA = 'C'    # pasivo y patrimonio: saldo = haber - debe


def periodo_balance(anio):
    """Periodo AAAAMMDD del balance anual (al 31 de diciembre)."""
    return '%04d1231' % anio


# ---------------------------------------------------------------------------
# Naturaleza de las cuentas (por account_type de Odoo)
# ---------------------------------------------------------------------------

def naturaleza_por_tipo(tipo_cuenta):
    """'D' (activo), 'C' (pasivo/patrimonio) o None si no va al estado.

    Las cuentas de resultado (ingresos/gastos) y las de orden no tienen rubro
    en el estado de situación: su saldo se traslada al patrimonio por el
    asiento de cierre.
    """
    tipo = tipo_cuenta or ''
    if tipo.startswith('asset'):
        return DEUDORA
    if tipo.startswith('liability') or tipo in ('equity', 'equity_unaffected'):
        return ACREEDORA
    return None


def es_cuenta_de_resultado(tipo_cuenta):
    tipo = tipo_cuenta or ''
    return tipo.startswith('income') or tipo.startswith('expense')


# ---------------------------------------------------------------------------
# Importes
# ---------------------------------------------------------------------------

def formatear_saldo(centimos):
    """Céntimos -> ``'1234.50'``; los negativos como ``'-1234.50'`` (Regla 1.0)."""
    signo = '-' if centimos < 0 else ''
    entero, resto = divmod(abs(centimos), 100)
    return '%s%d.%02d' % (signo, entero, resto)


def saldo_cuenta(naturaleza, debe, haber):
    """Saldo de una cuenta en su sentido natural (positivo = saldo normal)."""
    return debe - haber if naturaleza == DEUDORA else haber - debe


# ---------------------------------------------------------------------------
# Consolidación por rubro
# ---------------------------------------------------------------------------
# cuenta (dict): naturaleza ('D'/'C'), debe, haber (céntimos), rubro (código).

def consolidar_rubros(cuentas):
    """{código de rubro: saldo en céntimos}, sumando el saldo de sus cuentas.

    Cada cuenta aporta en SU sentido natural: una depreciación acumulada
    (activo con saldo acreedor) resta de su rubro, y una pérdida acumulada
    (patrimonio con saldo deudor) resta del patrimonio.
    """
    saldos = {}
    for cuenta in cuentas:
        if not cuenta.get('naturaleza') or not cuenta.get('rubro'):
            continue
        aporte = saldo_cuenta(cuenta['naturaleza'], cuenta['debe'], cuenta['haber'])
        saldos[cuenta['rubro']] = saldos.get(cuenta['rubro'], 0) + aporte
    return saldos


def resultado_no_cerrado(cuentas):
    """Resultado acumulado de las cuentas de ingresos/gastos aún sin cerrar.

    Positivo = ganancia, negativo = pérdida (haber - debe). Si el asiento de
    cierre ya se registró, estas cuentas suman cero.
    """
    return sum(c['haber'] - c['debe'] for c in cuentas)


def totales_situacion(cuentas, resultado=0):
    """(total activo, total pasivo y patrimonio) en céntimos.

    Se calculan sobre TODAS las cuentas de activo/pasivo/patrimonio, tengan o
    no rubro, para detectar un estado que no cuadra. ``resultado`` es el
    resultado aún no cerrado, que pertenece al patrimonio.
    """
    activo = sum(saldo_cuenta(c['naturaleza'], c['debe'], c['haber'])
                 for c in cuentas if c.get('naturaleza') == DEUDORA)
    pasivo_patrimonio = sum(saldo_cuenta(c['naturaleza'], c['debe'], c['haber'])
                            for c in cuentas if c.get('naturaleza') == ACREEDORA)
    return activo, pasivo_patrimonio + resultado


# ---------------------------------------------------------------------------
# Estructura 3.1
# ---------------------------------------------------------------------------

def linea_31(periodo, catalogo, rubro, saldo, estado='1'):
    """Línea TXT de la estructura 3.1 (5 campos y el palote final)."""
    rubro = str(rubro or '').strip()
    if not rubro or len(rubro) > 6:
        raise ValueError('Rubro de la Tabla 34 inválido: %r' % rubro)
    catalogo = str(catalogo or '').strip()
    if len(catalogo) != 2 or not catalogo.isdigit():
        raise ValueError('Código de catálogo (Tabla 22) inválido: %r' % catalogo)
    campos = [
        periodo,                   # 1 Periodo AAAAMMDD
        catalogo,                  # 2 Código del catálogo (Tabla 22)
        rubro,                     # 3 Código del rubro (Tabla 34)
        formatear_saldo(saldo),    # 4 Saldo del rubro contable
        estado,                    # 5 Estado de la operación
    ]
    assert len(campos) == CAMPOS_31
    return '|'.join(campos) + '|'


def filas_31(periodo, catalogo, saldos, estado='1'):
    """Líneas TXT del 3.1 ordenadas por rubro; los rubros en cero no se informan.

    C1, C2 y C3 son llave única: una fila por rubro, que es lo que devuelve
    ``consolidar_rubros``.
    """
    return [
        linea_31(periodo, catalogo, rubro, saldo, estado)
        for rubro, saldo in sorted(saldos.items())
        if saldo != 0
    ]
