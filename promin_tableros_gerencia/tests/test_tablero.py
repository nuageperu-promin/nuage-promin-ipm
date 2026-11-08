from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestTableroPedido(TransactionCase):

    def test_vista_consulta_y_agrupa(self):
        Tablero = self.env['promin.tablero.pedido']
        grupos = Tablero.read_group([], ['pedido_usd:sum', 'facturado_usd:sum'], ['linea_id'])
        self.assertIsInstance(grupos, list)

    def test_facturado_no_supera_pedido(self):
        for rec in self.env['promin.tablero.pedido'].search([], limit=200):
            self.assertLessEqual(rec.facturado_usd, rec.pedido_usd + 0.01)
