"""Funciones puras (sin Odoo) de los libros impresos: numeracion, saldos y paginacion.

Las medidas estan en puntos (A4 horizontal 841.89 x 595.28) y reproducen los
modelos "Estilo Clasico" entregados por PROMIN (Formato 5.1 y 6.1).
"""
from collections import OrderedDict

ALTO_FILA = 9.2          # separacion entre lineas de texto
ALTO_ASIENTO = 5.5       # espacio extra entre asientos (Diario)
ALTO_CUENTA = 11.5       # espacio extra entre cuentas (Mayor)
TOPE_DIARIO = 493.5      # borde inferior de la ultima fila; VAN va debajo
TOPE_MAYOR = 497.0
INICIO_CUERPO = 83.0
ALTO_TOTAL_GENERAL = 17.2   # linea de TOTALES GENERALES bajo la ultima fila
LIBROS = ('01', '05', '08', '14')   # Tabla 8 SUNAT: caja y bancos, diario, compras, ventas

TOL = 0.005


def redondear(valor):
    return round(valor + 0.0, 2)


def libro_por_tipo_diario(tipo):
    """Libro (Tabla 8) segun el tipo de diario de Odoo. Se puede forzar en el diario."""
    return {'bank': '01', 'cash': '01', 'purchase': '08', 'sale': '14'}.get(tipo, '05')


def fmt(valor):
    """Importe con miles y 2 decimales; vacio si es cero."""
    if valor is None or abs(valor) < TOL:
        return ''
    return '{:,.2f}'.format(valor)


def fmt_saldo(valor):
    """Saldo: siempre se imprime (cero => vacio como en el modelo)."""
    return fmt(valor)


def ordenar_lineas_asiento(lineas):
    """Primero las lineas al debe, luego al haber; dentro de cada grupo, en el orden de registro."""
    return sorted(lineas, key=lambda l: (0 if l['debe'] > 0 else 1, l.get('seq', 0), l['cuenta']))


def numerar_asientos(asientos):
    """Asigna 'vou' (correlativo dentro del libro y periodo).

    asientos: [{'id', 'libro', 'fecha' (date), 'cuo', 'lineas': [...]}].
    Orden: libro, fecha, cuo, id. Devuelve la lista ordenada y numerada.
    """
    orden = sorted(asientos, key=lambda a: (a['libro'], a['fecha'], a['cuo'], a['id']))
    contador = {}
    for a in orden:
        contador[a['libro']] = contador.get(a['libro'], 0) + 1
        a['vou'] = contador[a['libro']]
    return orden


# ---------------------------------------------------------------------------
# Libro Diario
# ---------------------------------------------------------------------------
def _fila_diario(asiento, linea, primera):
    return {
        'libro': asiento['libro'], 'vou': asiento['vou'], 'cuo': asiento['cuo'],
        'fecha': asiento['fecha'], 'doc': asiento.get('doc', ''), 'glosa': asiento.get('glosa', ''),
        'cuenta': linea['cuenta'], 'denominacion': linea['denominacion'],
        'debe': linea['debe'], 'haber': linea['haber'], 'primera': primera,
    }


def paginar_diario(asientos):
    """Reparte los asientos numerados en paginas con VIENEN/VAN y total general.

    Un asiento no se parte entre paginas salvo que no entre en una pagina completa.
    Devuelve [{'filas': [...], 'vienen': (debe, haber)|None, 'van': (debe, haber)|None,
               'total': (debe, haber)|None}].
    """
    paginas = []
    acum_d = acum_h = 0.0

    def nueva_pagina():
        pag = {'filas': [], 'vienen': (acum_d, acum_h) if paginas else None,
               'van': None, 'total': None, 'usado': 0.0}
        if paginas:   # la fila VIENEN ocupa una linea mas su separacion
            pag['usado'] = ALTO_FILA + ALTO_ASIENTO
        paginas.append(pag)
        return pag

    pag = nueva_pagina()
    disponible = TOPE_DIARIO - INICIO_CUERPO

    for a in asientos:
        lineas = a['lineas']
        if not lineas:
            continue
        alto = len(lineas) * ALTO_FILA + (ALTO_ASIENTO if pag['filas'] else 0.0)
        if pag['usado'] + alto > disponible:
            completo = len(lineas) * ALTO_FILA
            if completo <= disponible - (ALTO_FILA + ALTO_ASIENTO) and pag['filas']:
                pag['van'] = (acum_d, acum_h)
                pag = nueva_pagina()
        primera = True
        for l in lineas:
            sep = ALTO_ASIENTO if (primera and pag['filas']) else 0.0
            if pag['usado'] + sep + ALTO_FILA > disponible:
                pag['van'] = (acum_d, acum_h)
                pag = nueva_pagina()
                sep = 0.0
            pag['filas'].append(_fila_diario(a, l, primera))
            pag['usado'] += sep + ALTO_FILA
            acum_d += l['debe']
            acum_h += l['haber']
            primera = False

    # total general bajo la ultima fila; si no cabe, pasa a una hoja propia
    if pag['usado'] + ALTO_TOTAL_GENERAL + ALTO_FILA > (TOPE_DIARIO + 12.0) - INICIO_CUERPO:
        pag['van'] = (acum_d, acum_h)
        pag = nueva_pagina()
    pag['total'] = (acum_d, acum_h)
    for p in paginas:
        p.pop('usado', None)
    return paginas


# ---------------------------------------------------------------------------
# Libro Mayor
# ---------------------------------------------------------------------------
def armar_mayor(cuentas, solo_con_movimiento=True):
    """cuentas: [{'cuenta', 'denominacion', 'saldo_anterior', 'movs': [...]}].

    Cada mov: {'libro','vou','cuo','fecha','doc','glosa','debe','haber', ...}.
    Devuelve las cuentas con 'movs' ordenados y saldo corrido, y los totales.
    """
    resultado = []
    for c in sorted(cuentas, key=lambda x: x['cuenta']):
        saldo = c.get('saldo_anterior', 0.0) or 0.0
        movs = sorted(c['movs'], key=lambda m: (m['fecha'], m['libro'], m['vou'], m.get('cuo', '')))
        if solo_con_movimiento and not movs and abs(saldo) < TOL:
            continue
        deudor = saldo if saldo > 0 else 0.0
        acreedor = -saldo if saldo < 0 else 0.0
        filas = []
        for m in movs:
            saldo += m['debe'] - m['haber']
            deudor += m['debe']
            acreedor += m['haber']
            filas.append(dict(m, saldo=redondear(saldo)))
        resultado.append({
            'cuenta': c['cuenta'], 'denominacion': c['denominacion'],
            'saldo_anterior': c.get('saldo_anterior', 0.0) or 0.0,
            'movs': filas, 'deudor': redondear(deudor), 'acreedor': redondear(acreedor),
            'saldo': redondear(saldo),
        })
    total_d = redondear(sum(c['deudor'] for c in resultado))
    total_h = redondear(sum(c['acreedor'] for c in resultado))
    return resultado, (total_d, total_h)


def paginar_mayor(cuentas, totales):
    """Reparte el mayor en paginas. Cada cuenta se compone de elementos:
    'cuenta' (encabezado), 'anterior', 'mov' y 'total'. Se evita dejar el
    encabezado solo al final de una pagina o el total solo al inicio.
    """
    paginas = [{'items': [], 'total': None}]
    usado = 0.0
    disponible = TOPE_MAYOR - INICIO_CUERPO

    def colocar(items):
        nonlocal usado
        pag = paginas[-1]
        for it in items:
            alto = ALTO_FILA + (ALTO_CUENTA if it['tipo'] == 'cuenta' and pag['items'] else 0.0)
            pag['items'].append(dict(it, sep=alto - ALTO_FILA))
            usado += alto

    def alto_items(items, vacia):
        total = 0.0
        for k, it in enumerate(items):
            total += ALTO_FILA + (ALTO_CUENTA if it['tipo'] == 'cuenta' and not (vacia and k == 0) else 0.0)
        return total

    for c in cuentas:
        elementos = [{'tipo': 'cuenta', 'cuenta': c['cuenta'], 'denominacion': c['denominacion']},
                     {'tipo': 'anterior', 'saldo': c['saldo_anterior']}]
        elementos += [dict(m, tipo='mov') for m in c['movs']]
        elementos.append({'tipo': 'total', 'cuenta': c['cuenta'], 'deudor': c['deudor'],
                          'acreedor': c['acreedor'], 'saldo': c['saldo']})
        i = 0
        while i < len(elementos):
            pag = paginas[-1]
            vacia = not pag['items']
            # bloque minimo que debe ir junto: al inicio de cuenta (cuenta+anterior+1 mov), al final (ult mov+total)
            if i == 0:
                bloque = elementos[:min(3, len(elementos))]
            elif len(elementos) - i <= 2:
                bloque = elementos[i:]
            else:
                bloque = [elementos[i]]
            if usado + alto_items(bloque, vacia) > disponible and not vacia:
                paginas.append({'items': [], 'total': None})
                usado = 0.0
                continue
            colocar(bloque)
            i += len(bloque)
    # totales generales
    if usado + ALTO_TOTAL_GENERAL + ALTO_FILA > disponible:
        paginas.append({'items': [], 'total': None})
    paginas[-1]['total'] = totales
    return paginas
