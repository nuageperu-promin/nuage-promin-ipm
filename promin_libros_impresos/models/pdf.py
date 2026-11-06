"""Dibujo de los libros con reportlab (A4 horizontal, estilo clasico de PROMIN)."""
from io import BytesIO

from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

try:
    from . import calculo as c
except ImportError:   # prueba fuera de Odoo
    import calculo as c

ANCHO, ALTO = landscape(A4)
FUENTE = 'Helvetica'
NEGRITA = 'Helvetica-Bold'
T_CAB = 7.2
T_TIT = 8.2
T_COL = 6.6
T_CUERPO = 6.4
MARGEN_IZQ = 18.0
MARGEN_DER = 824.0


def _y(top, tam):
    """Convierte la coordenada superior (como en el modelo) a la base del texto."""
    return ALTO - top - tam * 0.80


def _texto(cv, x, top, texto, tam=T_CUERPO, fuente=FUENTE, derecha=False, centro=False):
    if texto is None or texto == '':
        return
    cv.setFont(fuente, tam)
    y = _y(top, tam)
    if derecha:
        cv.drawRightString(x, y, texto)
    elif centro:
        cv.drawCentredString(x, y, texto)
    else:
        cv.drawString(x, y, texto)


def _recortar(cv, texto, ancho, fuente=FUENTE, tam=T_CUERPO):
    """Recorta el texto para que no invada la columna siguiente."""
    texto = texto or ''
    while texto and cv.stringWidth(texto, fuente, tam) > ancho:
        texto = texto[:-1]
    return texto


def _linea(cv, x0, x1, top, grosor=0.5):
    cv.setLineWidth(grosor)
    cv.line(x0, ALTO - top, x1, ALTO - top)


def _cabecera(cv, cab, titulo, folio, columnas):
    _texto(cv, 22, 18.3, cab['empresa'], T_CAB)
    _texto(cv, 22, 27.0, 'PERIODO ' + cab['periodo'], T_CAB)
    _texto(cv, 22, 35.4, cab['direccion'], T_CAB)
    _texto(cv, 22, 43.8, 'R.U.C.: ' + cab['ruc'], T_CAB)
    _texto(cv, ANCHO / 2, 25.9, titulo, T_TIT, centro=True)
    _texto(cv, 820, 35.4, 'Pag. %05d' % folio, T_CAB, derecha=True)
    cv.setLineWidth(0.5)
    cv.rect(MARGEN_IZQ, ALTO - 76.0, MARGEN_DER - MARGEN_IZQ, 20.0, stroke=1, fill=0)
    for x, top, texto, derecha in columnas:
        _texto(cv, x, top, texto, T_COL, derecha=derecha)


def _abrir():
    buf = BytesIO()
    cv = canvas.Canvas(buf, pagesize=(ANCHO, ALTO))
    return buf, cv


def _fecha(f):
    return f.strftime('%d/%m/%Y')


# ---------------------------------------------------------------------------
# Libro Diario - Formato 5.1
# ---------------------------------------------------------------------------
COL_DIARIO = [
    (24, 58.8, 'Libro', False), (24, 66.4, 'T.8', False), (65, 58.8, 'Vou', True),
    (70, 58.8, 'C.U.O.', False), (144, 58.8, 'Fecha', False), (184, 58.8, 'Doc. Sustent.', False),
    (242, 58.8, 'G L O S A', False), (458, 58.8, 'Cuenta', False), (490, 58.8, 'Denominación', False),
    (741, 58.8, 'Debe', True), (815, 58.8, 'Haber', True),
]


def render_diario(cab, paginas, folio_inicial=1):
    buf, cv = _abrir()
    cv.setTitle('Formato 5.1: Libro Diario')
    cv.setAuthor(cab['empresa'])
    for n, pag in enumerate(paginas):
        _cabecera(cv, cab, 'FORMATO 5.1: "LIBRO DIARIO"', folio_inicial + n, COL_DIARIO)
        top = c.INICIO_CUERPO
        if pag['vienen']:
            _texto(cv, 655, top, 'VIENEN ......', T_CUERPO, NEGRITA, derecha=True)
            _texto(cv, 741, top, c.fmt(pag['vienen'][0]) or '0.00', T_CUERPO, NEGRITA, derecha=True)
            _texto(cv, 815, top, c.fmt(pag['vienen'][1]) or '0.00', T_CUERPO, NEGRITA, derecha=True)
            top += c.ALTO_FILA + c.ALTO_ASIENTO
        primera_fila = True
        for f in pag['filas']:
            if f['primera'] and not primera_fila:
                top += c.ALTO_ASIENTO
            primera_fila = False
            _texto(cv, 24, top, f['libro'])
            _texto(cv, 65, top, str(f['vou']), derecha=True)
            _texto(cv, 70, top, _recortar(cv, f['cuo'], 70))
            _texto(cv, 144, top, _fecha(f['fecha']))
            _texto(cv, 184, top, _recortar(cv, f['doc'], 54))
            _texto(cv, 242, top, _recortar(cv, f['glosa'], 210))
            _texto(cv, 458, top, f['cuenta'])
            _texto(cv, 490, top, _recortar(cv, f['denominacion'], 200))
            if f['debe']:
                _texto(cv, 741, top, c.fmt(f['debe']), derecha=True)
            if f['haber']:
                _texto(cv, 815, top, c.fmt(f['haber']), derecha=True)
            top += c.ALTO_FILA
        if pag['total']:
            _linea(cv, 676, 743, top + 2.9)
            _linea(cv, 750, 817, top + 2.9)
            top += 8.0
            _texto(cv, 574, top, 'TOTALES GENERALES ......', T_CUERPO, NEGRITA, derecha=True)
            _texto(cv, 741, top, c.fmt(pag['total'][0]) or '0.00', T_CUERPO, NEGRITA, derecha=True)
            _texto(cv, 815, top, c.fmt(pag['total'][1]) or '0.00', T_CUERPO, NEGRITA, derecha=True)
        if pag['van']:
            _linea(cv, MARGEN_IZQ, MARGEN_DER, top - 1.6)
            _texto(cv, 655, top + 3.0, 'VAN ......', T_CUERPO, NEGRITA, derecha=True)
            _texto(cv, 741, top + 3.0, c.fmt(pag['van'][0]) or '0.00', T_CUERPO, NEGRITA, derecha=True)
            _texto(cv, 815, top + 3.0, c.fmt(pag['van'][1]) or '0.00', T_CUERPO, NEGRITA, derecha=True)
        cv.showPage()
    cv.save()
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Libro Mayor - Formato 6.1
# ---------------------------------------------------------------------------
COL_MAYOR = [
    (24, 58.8, 'Libro', False), (24, 66.4, 'T.8', False), (65, 58.8, 'Vou', True),
    (70, 58.8, 'N° Correlativo', False), (70, 66.4, 'Libro Diario', False),
    (142, 58.8, 'Fecha', False), (182, 58.8, 'Doc. Sustent.', False),
    (238, 58.8, 'DESCRIPCION O GLOSA DE LA OPERACION', False),
    (609, 58.8, 'Deudor', True), (685, 58.8, 'Acreedor', True), (765, 58.8, 'Saldo', True),
]


def render_mayor(cab, paginas, fecha_inicio, folio_inicial=1):
    buf, cv = _abrir()
    cv.setTitle('Formato 6.1: Libro Mayor')
    cv.setAuthor(cab['empresa'])
    for n, pag in enumerate(paginas):
        _cabecera(cv, cab, 'FORMATO 6.1: "LIBRO MAYOR"', folio_inicial + n, COL_MAYOR)
        top = c.INICIO_CUERPO
        primero = True
        for it in pag['items']:
            if it['tipo'] == 'cuenta':
                if not primero:
                    top += c.ALTO_CUENTA
                _texto(cv, 70, top, 'CUENTA ' + it['cuenta'], T_CUERPO, NEGRITA)
                _texto(cv, 238, top, _recortar(cv, it['denominacion'], 340, NEGRITA), T_CUERPO, NEGRITA)
            elif it['tipo'] == 'anterior':
                _texto(cv, 142, top, _fecha(fecha_inicio))
                _texto(cv, 238, top, 'SALDO ANTERIOR')
                s = it['saldo']
                if abs(s) >= c.TOL:
                    _texto(cv, 609 if s > 0 else 685, top, c.fmt(abs(s)), derecha=True)
                    _texto(cv, 765, top, c.fmt(s), derecha=True)
            elif it['tipo'] == 'mov':
                _texto(cv, 24, top, it['libro'])
                _texto(cv, 65, top, str(it['vou']), derecha=True)
                _texto(cv, 70, top, _recortar(cv, it['cuo'], 70))
                _texto(cv, 142, top, _fecha(it['fecha']))
                _texto(cv, 182, top, _recortar(cv, it['doc'], 54))
                _texto(cv, 238, top, _recortar(cv, it['glosa'], 290))
                if it['debe']:
                    _texto(cv, 609, top, c.fmt(it['debe']), derecha=True)
                if it['haber']:
                    _texto(cv, 685, top, c.fmt(it['haber']), derecha=True)
                _texto(cv, 765, top, c.fmt(it['saldo']) or '0.00', derecha=True)
            elif it['tipo'] == 'total':
                _linea(cv, 542, 611, top - 2.6)
                _linea(cv, 618, 687, top - 2.6)
                _linea(cv, 694, 767, top - 2.6)
                top += 2.5
                _texto(cv, 238, top, 'TOTAL CUENTA %s ......' % it['cuenta'], T_CUERPO, NEGRITA)
                _texto(cv, 609, top, c.fmt(it['deudor']), T_CUERPO, NEGRITA, derecha=True)
                _texto(cv, 685, top, c.fmt(it['acreedor']), T_CUERPO, NEGRITA, derecha=True)
                _texto(cv, 765, top, c.fmt(it['saldo']) or '0.00', T_CUERPO, NEGRITA, derecha=True)
            top += c.ALTO_FILA
            primero = False
        if pag['total']:
            _linea(cv, 542, 611, top + 8.4)
            _linea(cv, 618, 687, top + 8.4)
            top += 13.5
            _texto(cv, 238, top, 'TOTALES GENERALES ......', T_CUERPO, NEGRITA)
            _texto(cv, 609, top, c.fmt(pag['total'][0]) or '0.00', T_CUERPO, NEGRITA, derecha=True)
            _texto(cv, 685, top, c.fmt(pag['total'][1]) or '0.00', T_CUERPO, NEGRITA, derecha=True)
        cv.showPage()
    cv.save()
    return buf.getvalue()
