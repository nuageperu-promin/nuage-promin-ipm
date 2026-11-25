from odoo import fields, models

from .vendor_evaluation import RATINGS


class ResPartner(models.Model):
    _inherit = 'res.partner'

    nuage_evaluation_count = fields.Integer('Evaluaciones', compute='_compute_nuage_evaluation')
    nuage_last_rating = fields.Selection(RATINGS, string='Última categoría',
                                         compute='_compute_nuage_evaluation')
    nuage_last_score = fields.Float('Última nota', compute='_compute_nuage_evaluation', digits=(5, 1))

    def _compute_nuage_evaluation(self):
        Evaluation = self.env['nuage.vendor.evaluation']
        ids = [p._origin.id for p in self if p._origin.id]
        counts = {}
        last_confirmed = {}
        if ids:
            counts = {partner.id: count for partner, count in
                      Evaluation._read_group([('partner_id', 'in', ids)], ['partner_id'], ['__count'])}
            confirmed = Evaluation.search([('partner_id', 'in', ids), ('state', '=', 'confirmed')],
                                          order='date_to desc, id desc')
            for evaluation in confirmed:
                last_confirmed.setdefault(evaluation.partner_id.id, evaluation)
        for partner in self:
            pid = partner._origin.id
            last = last_confirmed.get(pid)
            partner.nuage_evaluation_count = counts.get(pid, 0)
            partner.nuage_last_rating = last.rating if last else False
            partner.nuage_last_score = last.total_score if last else 0.0

    def action_view_nuage_evaluations(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Evaluaciones',
            'res_model': 'nuage.vendor.evaluation',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }
