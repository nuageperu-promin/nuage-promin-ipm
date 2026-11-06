"""Prueba: reconstruye los modelos de PROMIN a partir de sus PDF y compara totales y paginas.

Uso: python3 test_modelos.py <Libro_Diario.pdf> <Libro_Mayor.pdf> [carpeta_salida]
"""
import datetime
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'models'))
import calculo as c   # noqa: E402
import pdf            # noqa: E402


def texto(pdf_path):
    return subprocess.run(['pdftotext', '-layout', pdf_path, '-'], capture_output=True, text=True).stdout


def num(s):
    return float(s.replace(',', ''))


def parsear_diario(pdf_path):
    import pdfplumber
    asientos, orden = {}, []
    with pdfplumber.open(pdf_path) as doc:
        for pag in doc.pages:
            filas = {}
            for w in pag.extract_words():
                filas.setdefault(round(w['top']), []).append(w)
            for top in sorted(filas):
                ws = sorted(filas[top], key=lambda w: w['x0'])
                def col(x0, x1):
                    return ' '.join(w['text'] for w in ws if x0 <= w['x0'] < x1)
                libro, cuenta = col(20, 40), col(455, 488)
                if not (re.fullmatch(r'\d\d', libro) and re.fullmatch(r'\d{4,6}', cuenta)):
                    continue
                vou, cuo, fecha = col(45, 68), col(68, 142), col(142, 182)
                doc_s, glosa, denom = col(182, 240), col(240, 455), col(488, 700)
                montos = [w for w in ws if w['x0'] >= 700 and re.fullmatch(r'[\d,]+\.\d\d', w['text'])]
                d, mth, y = map(int, fecha.split('/')[0:3])
                mth, d, y = int(fecha.split('/')[1]), int(fecha.split('/')[0]), int(fecha.split('/')[2])
                clave = (libro, int(vou))
                if clave not in asientos:
                    asientos[clave] = {'id': len(asientos) + 1, 'libro': libro, 'fecha': datetime.date(y, mth, d),
                                       'cuo': cuo, 'doc': doc_s, 'glosa': glosa, 'lineas': []}
                    orden.append(clave)
                debe = sum(num(w['text']) for w in montos if w['x1'] < 760)
                haber = sum(num(w['text']) for w in montos if w['x1'] >= 760)
                asientos[clave]['lineas'].append({'seq': len(asientos[clave]['lineas']), 'cuenta': cuenta, 'denominacion': denom,
                                                  'debe': debe, 'haber': haber})
    return [asientos[k] for k in orden]


def main():
    diario_pdf, mayor_pdf = sys.argv[1], sys.argv[2]
    salida = sys.argv[3] if len(sys.argv) > 3 else '.'
    cab = {'empresa': 'EMPRESA DEMO S.A.C.', 'periodo': 'OCTUBRE 2026',
           'direccion': 'AV. EJEMPLO 123 - SAN ISIDRO - LIMA', 'ruc': '20000000001'}

    asientos = parsear_diario(diario_pdf)
    print('asientos leidos:', len(asientos), 'lineas:', sum(len(a['lineas']) for a in asientos))
    numerados = c.numerar_asientos(asientos)
    for a in numerados:
        a['lineas'] = c.ordenar_lineas_asiento(a['lineas'])
    paginas = c.paginar_diario(numerados)
    total = paginas[-1]['total']
    print('DIARIO paginas:', len(paginas), '(modelo 4)  total general:', total, '(modelo 217,253.00)')
    print('  VAN pagina 1:', paginas[0]['van'], '(modelo 85,034.00)')
    assert abs(paginas[0]['van'][0] - 85034.0) < 0.01
    assert abs(total[0] - 217253.0) < 0.01 and abs(total[1] - 217253.0) < 0.01
    open(os.path.join(salida, 'diario.pdf'), 'wb').write(pdf.render_diario(cab, paginas))

    # Mayor: cada linea del diario es un movimiento de su cuenta
    saldos_ant = {'1041': 25000.0, '1212': 4500.0, '20111': 12000.0}
    cuentas = {}
    for a in numerados:
        for l in a['lineas']:
            cu = cuentas.setdefault(l['cuenta'], {'cuenta': l['cuenta'], 'denominacion': l['denominacion'],
                                                  'saldo_anterior': saldos_ant.get(l['cuenta'], 0.0), 'movs': []})
            cu['movs'].append({'libro': a['libro'], 'vou': a['vou'], 'cuo': a['cuo'], 'fecha': a['fecha'],
                               'doc': a['doc'], 'glosa': a['glosa'], 'debe': l['debe'], 'haber': l['haber']})
    for k, v in saldos_ant.items():
        cuentas.setdefault(k, {'cuenta': k, 'denominacion': '', 'saldo_anterior': v, 'movs': []})
    lista, totales = c.armar_mayor(list(cuentas.values()))
    pm = c.paginar_mayor(lista, totales)
    print('MAYOR cuentas:', len(lista), 'paginas:', len(pm), '(modelo 6)  totales:', totales, '(modelo 258,753.00 deudor; el acreedor del modelo es sintetico)')
    fin = {x['cuenta']: x['saldo'] for x in lista}
    print('  saldo 1041:', fin['1041'], '(modelo 73,734.00)  1212:', fin['1212'], '(69,636.00)  20111:', fin['20111'], '(12,800.00)')
    assert abs(totales[0] - 258753.0) < 0.01 and abs(totales[1] - 217253.0) < 0.01
    assert abs(fin['1041'] - 73734.0) < 0.01 and abs(fin['1212'] - 69636.0) < 0.01
    open(os.path.join(salida, 'mayor.pdf'), 'wb').write(pdf.render_mayor(cab, pm, datetime.date(2026, 10, 1)))
    print('OK')


if __name__ == '__main__':
    main()
