# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
"""Formato del Libro 1 (Caja y Bancos) del PLE de SUNAT.

Funciones puras, sin dependencia de Odoo: reciben diccionarios con datos ya
resueltos y devuelven las líneas del TXT. Se separan del modelo para poder
probar el formato con ``python -m unittest`` sin levantar una base.

Fuente: «Estructura del PLE» de SUNAT, hojas «1 Libro Caja y Bancos» y
«Reglas Generales».

  1.1 (010100) Detalle de los movimientos del efectivo ...... 19 campos
  1.2 (010200) Detalle de los movimientos de la cuenta corriente 15 campos

Los importes viajan en CÉNTIMOS (enteros) hasta el momento de formatear:
sumar flotantes de dos decimales dejaba diferencias de un céntimo en la
consolidación.
"""
import re
from decimal import Decimal, ROUND_HALF_UP

CAMPOS_11 = 19
CAMPOS_12 = 15

# Reglas de tipo y número de documento (hoja «Reglas Generales»):
# tipo -> (longitud, 'N' numérico / 'A' alfanumérico, fija?, módulo 11?)
REGLAS_DOCUMENTO = {
    '0': (15, 'A', False, False),   # Otros
    '1': (8, 'N', True, False),     # DNI / Libreta electoral
    '4': (12, 'A', False, False),   # Carnet de extranjería
    '6': (11, 'N', True, True),     # RUC
    '7': (12, 'A', False, False),   # Pasaporte
    'A': (15, 'N', True, False),    # Cédula diplomática
}

_PESOS_RUC = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)


# ---------------------------------------------------------------------------
# Texto
# ---------------------------------------------------------------------------

def sanear_texto(valor, max_len=200):
    """Texto libre del PLE (Regla 2.0): sin ``|``, ``/`` ni ``\\``.

    Los reemplaza por espacio, como ``ple.report.templ._formato_glosa``.
    """
    texto = str(valor or '')
    for caracter in ('|', '/', '\\'):
        texto = texto.replace(caracter, ' ')
    return ' '.join(texto.split())[:max_len].strip()


def sanear_alfanumerico(valor, max_len, desde_cola=False):
    """Campo alfanumérico (Regla 3.0): no admite ``|``, ``/`` ni ``\\``.

    Se reemplazan por guion para no perder la legibilidad del número
    (``BNK1/2026/00012`` -> ``BNK1-2026-00012``). Con ``desde_cola`` el
    recorte conserva el final, que es donde está la parte única de un nombre
    de asiento.
    """
    texto = str(valor or '')
    for caracter in ('|', '/', '\\'):
        texto = texto.replace(caracter, '-')
    texto = ' '.join(texto.split()).strip()
    if len(texto) > max_len:
        texto = texto[-max_len:] if desde_cola else texto[:max_len]
    return texto.strip()


# ---------------------------------------------------------------------------
# Importes
# ---------------------------------------------------------------------------

def a_centimos(importe):
    """Importe (float, Decimal o None) -> céntimos enteros, redondeo comercial."""
    valor = Decimal(str(importe or 0)) * 100
    return int(valor.to_integral_value(rounding=ROUND_HALF_UP))


def formatear_importe(centimos):
    """Céntimos no negativos -> ``'1234.50'`` (sin separador de miles)."""
    if centimos < 0:
        raise ValueError('El PLE separa debe y haber: no admite importes negativos aquí')
    entero, resto = divmod(centimos, 100)
    return '%d.%02d' % (entero, resto)


def dividir_neto(neto):
    """Neto en céntimos -> (debe, haber). Debe y haber son excluyentes."""
    return (neto, 0) if neto >= 0 else (0, -neto)


# ---------------------------------------------------------------------------
# Catálogos
# ---------------------------------------------------------------------------

def normalizar_codigo_banco(valor):
    """Código de entidad financiera (Tabla 3, 2 dígitos). '99' = otros."""
    texto = str(valor or '').strip()
    if texto.isdigit() and 1 <= len(texto) <= 2:
        return texto.zfill(2)
    return '99'


def normalizar_medio_pago(valor):
    """Medio de pago (Tabla 1, 3 dígitos). '999' = otros medios de pago."""
    texto = str(valor or '').strip()
    if texto.isdigit() and 1 <= len(texto) <= 3:
        return texto.zfill(3)
    return '999'


def ruc_valido(ruc):
    """RUC de 11 dígitos con dígito verificador módulo 11."""
    ruc = str(ruc or '')
    if len(ruc) != 11 or not ruc.isdigit():
        return False
    suma = sum(int(d) * p for d, p in zip(ruc[:10], _PESOS_RUC))
    return (11 - suma % 11) % 10 == int(ruc[10])


def documento_girador(tipo, numero):
    """(tipo, número) del girador/beneficiario según las reglas de SUNAT.

    Si el documento no existe o no cumple la regla de su tipo (longitud,
    numérico/alfanumérico, módulo 11) devuelve ``('-', '-')``: es lo que la
    estructura pide cuando no hay documento, y evita que el validador rechace
    la fila por un DNI de 7 dígitos o un RUC con dígito verificador errado.
    """
    tipo = str(tipo or '').strip()
    numero = str(numero or '').strip()
    regla = REGLAS_DOCUMENTO.get(tipo)
    if not regla or not numero:
        return ('-', '-')
    longitud, clase, fija, modulo11 = regla
    if fija and len(numero) != longitud:
        return ('-', '-')
    if not fija and not 1 <= len(numero) <= longitud:
        return ('-', '-')
    if clase == 'N' and not numero.isdigit():
        return ('-', '-')
    if clase == 'A' and not re.fullmatch(r'[A-Za-z0-9]+', numero):
        return ('-', '-')
    if modulo11 and not ruc_valido(numero):
        return ('-', '-')
    return (tipo, numero)


# ---------------------------------------------------------------------------
# Estructura 1.1 — movimientos del efectivo
# ---------------------------------------------------------------------------
# Registro (dict): periodo, cuo, correlativo, cuenta, moneda, tipo_cp, serie,
# numero, f_contable, f_venc, f_op, glosa, debe, haber (céntimos), estado.

def consolidar_11(registros):
    """Una fila por llave única de SUNAT: (C1, C2, C3, C4, C10).

    Un asiento con varias líneas a la misma cuenta de efectivo repetiría la
    llave y el validador rechaza el archivo. Se agrupa sumando en NETO
    (debe - haber) y se vuelve a partir en debe/haber, porque los campos 16 y
    17 son excluyentes. El movimiento neto del asiento no cambia.
    """
    consolidados = {}
    for registro in registros:
        llave = (registro['periodo'], registro['cuo'], registro['correlativo'],
                 registro['cuenta'], registro['numero'])
        neto = registro['debe'] - registro['haber']
        if llave in consolidados:
            consolidados[llave]['_neto'] += neto
        else:
            nuevo = dict(registro)
            nuevo['_neto'] = neto
            consolidados[llave] = nuevo
    resultado = []
    for registro in consolidados.values():
        registro['debe'], registro['haber'] = dividir_neto(registro.pop('_neto'))
        resultado.append(registro)
    return resultado


def linea_11(registro):
    """Línea TXT de la estructura 1.1 (19 campos y el palote final)."""
    campos = [
        registro['periodo'],                                  # 1  Periodo AAAAMM00
        sanear_alfanumerico(registro['cuo'], 40),             # 2  CUO
        sanear_alfanumerico(registro['correlativo'], 10),     # 3  Correlativo (A/M/C)
        registro['cuenta'],                                   # 4  Cuenta contable
        '',                                                   # 5  Unidad de operación
        '',                                                   # 6  Centro de costos
        registro['moneda'],                                   # 7  Tipo de moneda
        registro['tipo_cp'] or '00',                          # 8  Tipo de comprobante (Tabla 10)
        sanear_alfanumerico(registro['serie'], 20),           # 9  Serie
        sanear_alfanumerico(registro['numero'], 20, True),    # 10 Número
        registro['f_contable'],                               # 11 Fecha contable
        registro['f_venc'],                                   # 12 Fecha de vencimiento
        registro['f_op'],                                     # 13 Fecha de la operación
        sanear_texto(registro['glosa'], 200),                 # 14 Glosa
        '',                                                   # 15 Glosa referencial
        formatear_importe(registro['debe']),                  # 16 Debe
        formatear_importe(registro['haber']),                 # 17 Haber
        '',                                                   # 18 Dato estructurado
        registro['estado'],                                   # 19 Estado de la operación
    ]
    assert len(campos) == CAMPOS_11
    return '|'.join(campos) + '|'


# ---------------------------------------------------------------------------
# Estructura 1.2 — movimientos de la cuenta corriente
# ---------------------------------------------------------------------------
# Registro (dict): periodo, cuo, correlativo, banco, cuenta_bancaria, f_op,
# medio_pago, descripcion, tipo_doc, nro_doc, razon_social, nro_transaccion,
# debe, haber (céntimos), estado.

def consolidar_12(registros):
    """Una fila por llave única de SUNAT: (C1, C2, C3, C4, C5).

    Igual que en 1.1 se agrupa en neto. Además:
      * si las líneas fusionadas tienen girador distinto, la operación es
        múltiple: documento '-' y razón social 'varios' (regla de C9-C11);
      * las filas con neto 0.00 se descartan: C13 y C14 no pueden ser ambos
        0.00 en esta estructura.
    """
    consolidados = {}
    for registro in registros:
        llave = (registro['periodo'], registro['cuo'], registro['correlativo'],
                 registro['banco'], registro['cuenta_bancaria'])
        neto = registro['debe'] - registro['haber']
        if llave in consolidados:
            previo = consolidados[llave]
            previo['_neto'] += neto
            if (previo['tipo_doc'], previo['nro_doc'], previo['razon_social']) != (
                    registro['tipo_doc'], registro['nro_doc'], registro['razon_social']):
                previo['tipo_doc'], previo['nro_doc'] = '-', '-'
                previo['razon_social'] = 'varios'
        else:
            nuevo = dict(registro)
            nuevo['_neto'] = neto
            consolidados[llave] = nuevo
    resultado = []
    for registro in consolidados.values():
        neto = registro.pop('_neto')
        if neto == 0:
            continue
        registro['debe'], registro['haber'] = dividir_neto(neto)
        resultado.append(registro)
    return resultado


def linea_12(registro):
    """Línea TXT de la estructura 1.2 (15 campos y el palote final)."""
    tipo_doc, nro_doc = documento_girador(registro['tipo_doc'], registro['nro_doc'])
    razon_social = sanear_texto(registro['razon_social'], 200)
    if not razon_social:
        razon_social = 'varios'
    campos = [
        registro['periodo'],                                          # 1  Periodo AAAAMM00
        sanear_alfanumerico(registro['cuo'], 40),                     # 2  CUO
        sanear_alfanumerico(registro['correlativo'], 10),             # 3  Correlativo
        normalizar_codigo_banco(registro['banco']),                   # 4  Entidad financiera
        sanear_alfanumerico(registro['cuenta_bancaria'], 30),         # 5  Cuenta bancaria
        registro['f_op'],                                             # 6  Fecha de la operación
        normalizar_medio_pago(registro['medio_pago']),                # 7  Medio de pago
        sanear_texto(registro['descripcion'], 200) or 'MOVIMIENTO BANCARIO',  # 8
        tipo_doc,                                                     # 9  Tipo doc girador
        sanear_alfanumerico(nro_doc, 15),                             # 10 Nro doc girador
        razon_social,                                                 # 11 Razón social
        sanear_alfanumerico(registro['nro_transaccion'], 20, True),   # 12 Nro de transacción
        formatear_importe(registro['debe']),                          # 13 Parte deudora
        formatear_importe(registro['haber']),                         # 14 Parte acreedora
        registro['estado'],                                           # 15 Estado de la operación
    ]
    assert len(campos) == CAMPOS_12
    return '|'.join(campos) + '|'
