from datetime import date, datetime

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestVendorEvaluation(TransactionCase):

    def setUp(self):
        super().setUp()
        self.partner = self.env['res.partner'].create({'name': 'Proveedor de prueba'})
        self.evaluation = self.env['nuage.vendor.evaluation'].create({'partner_id': self.partner.id})

    def test_lines_created_from_criteria(self):
        self.assertEqual(len(self.evaluation.line_ids),
                         self.env['nuage.vendor.criterion'].search_count([]))

    def test_score_and_rating(self):
        self.evaluation.line_ids.write({'score': '5'})
        self.assertAlmostEqual(self.evaluation.total_score, 100.0)
        self.assertEqual(self.evaluation.rating, 'A')
        self.evaluation.line_ids.write({'score': '1'})
        self.assertAlmostEqual(self.evaluation.total_score, 20.0)
        self.assertEqual(self.evaluation.rating, 'D')

    def test_confirm_requires_all_scores(self):
        with self.assertRaises(UserError):
            self.evaluation.action_confirm()
        self.evaluation.line_ids.write({'score': '4'})
        self.evaluation.action_confirm()
        self.assertEqual(self.evaluation.state, 'confirmed')

    def test_weight_is_frozen_on_line(self):
        line = self.evaluation.line_ids[0]
        original = line.weight
        line.criterion_id.weight = original + 10
        self.assertEqual(line.weight, original)


@tagged('post_install', '-at_install')
class TestVendorEvaluationDeliveries(TransactionCase):
    """Cálculo de entregas a tiempo con recepciones reales de compra."""

    def setUp(self):
        super().setUp()
        self.env.user.tz = 'America/Lima'
        self.partner = self.env['res.partner'].create({'name': 'Proveedor entregas'})
        self.product = self.env['product.product'].create({'name': 'Producto de prueba', 'type': 'consu'})

    def _receive(self, planned, done):
        """Crea y confirma una OC con fecha prevista `planned`, la recibe y fija la fecha real `done`
        (ambas en UTC)."""
        po = self.env['purchase.order'].create({
            'partner_id': self.partner.id,
            'order_line': [Command.create({
                'product_id': self.product.id, 'product_qty': 1.0, 'price_unit': 10.0,
                'date_planned': planned,
            })],
        })
        po.button_confirm()
        picking = po.picking_ids[:1]
        picking.move_ids.write({'quantity': 1.0, 'picked': True})
        picking.with_context(skip_backorder=True).button_validate()
        picking.date_done = done
        return picking

    def _evaluation(self, date_from, date_to):
        return self.env['nuage.vendor.evaluation'].create({
            'partner_id': self.partner.id, 'date_from': date_from, 'date_to': date_to})

    def test_on_time_rate_and_delivery_score(self):
        # Lima = UTC-5. Una recepción a tiempo y otra tarde, ambas dentro del período.
        self._receive(datetime(2026, 6, 12, 15, 0), datetime(2026, 6, 10, 15, 0))   # a tiempo
        self._receive(datetime(2026, 6, 5, 15, 0), datetime(2026, 6, 10, 15, 0))    # 5 días tarde
        evaluation = self._evaluation(date(2026, 6, 1), date(2026, 6, 30))
        evaluation.action_compute_deliveries()
        self.assertEqual(evaluation.deliveries_total, 2)
        self.assertEqual(evaluation.deliveries_on_time, 1)
        self.assertAlmostEqual(evaluation.on_time_rate, 50.0)
        delivery_line = evaluation.line_ids.filtered('is_delivery')
        self.assertTrue(delivery_line)
        self.assertEqual(delivery_line.score, '2')

    def test_last_evening_of_period_is_included(self):
        # 22:00 en Lima del 15/06 = 03:00 UTC del 16/06: debe contar dentro del período que termina el 15/06.
        self._receive(datetime(2026, 6, 15, 20, 0), datetime(2026, 6, 16, 3, 0))
        evaluation = self._evaluation(date(2026, 6, 1), date(2026, 6, 15))
        evaluation.action_compute_deliveries()
        self.assertEqual(evaluation.deliveries_total, 1)
        self.assertEqual(evaluation.deliveries_on_time, 1)

    def test_previous_evening_before_period_is_excluded(self):
        # 22:00 en Lima del 31/05 = 03:00 UTC del 01/06: pertenece a mayo, no a un período que empieza el 01/06.
        self._receive(datetime(2026, 5, 31, 20, 0), datetime(2026, 6, 1, 3, 0))
        evaluation = self._evaluation(date(2026, 6, 1), date(2026, 6, 15))
        with self.assertRaises(UserError):
            evaluation.action_compute_deliveries()

    def test_no_deliveries_raises(self):
        evaluation = self._evaluation(date(2026, 6, 1), date(2026, 6, 15))
        with self.assertRaises(UserError):
            evaluation.action_compute_deliveries()


@tagged('post_install', '-at_install')
class TestVendorEvaluationSecurity(TransactionCase):

    def setUp(self):
        super().setUp()
        self.partner = self.env['res.partner'].create({'name': 'Proveedor seguridad'})
        self.evaluation = self.env['nuage.vendor.evaluation'].create({'partner_id': self.partner.id})
        self.evaluation.line_ids.write({'score': '4'})
        self.evaluation.action_confirm()
        group_user = self.env.ref('base.group_user')
        self.buyer = self.env['res.users'].create({
            'name': 'Comprador', 'login': 'comprador_eval',
            'group_ids': [Command.set([group_user.id, self.env.ref('purchase.group_purchase_user').id])],
        })
        self.manager = self.env['res.users'].create({
            'name': 'Jefe de compras', 'login': 'jefe_eval',
            'group_ids': [Command.set([group_user.id, self.env.ref('purchase.group_purchase_manager').id])],
        })

    def test_only_manager_can_reopen_confirmed(self):
        with self.assertRaises(UserError):
            self.evaluation.with_user(self.buyer).action_draft()
        self.assertEqual(self.evaluation.state, 'confirmed')
        self.evaluation.with_user(self.manager).action_draft()
        self.assertEqual(self.evaluation.state, 'draft')

    def test_confirmed_lines_are_locked(self):
        line = self.evaluation.line_ids[0]
        with self.assertRaises(UserError):
            line.write({'score': '1'})
        self.evaluation.with_user(self.manager).action_draft()
        line.write({'score': '1'})
        self.assertEqual(line.score, '1')

    def test_partner_counters(self):
        self.partner.invalidate_recordset()
        self.assertEqual(self.partner.nuage_evaluation_count, 1)
        self.assertEqual(self.partner.nuage_last_rating, self.evaluation.rating)
        self.assertAlmostEqual(self.partner.nuage_last_score, self.evaluation.total_score)
