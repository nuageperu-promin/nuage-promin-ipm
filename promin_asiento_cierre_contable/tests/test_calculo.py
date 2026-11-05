import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'models'))
import calculo as c

assert c.destino_resultado(-100) == 'utilidad'
assert c.destino_resultado(250.5) == 'perdida'
assert c.destino_resultado(0.001) is None
g = [{'balance': 500.0, 'amount_currency': 500.0}, {'balance': -800.0, 'amount_currency': -800.0}]
total = sum(l['balance'] for l in g)
cierre = c.invertir(g) + [{'balance': total, 'amount_currency': total}]
assert c.esta_cuadrado(cierre) and c.destino_resultado(total) == 'utilidad'
print('OK')
