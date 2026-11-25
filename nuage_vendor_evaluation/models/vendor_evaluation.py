from datetime import datetime, time, timedelta

import pytz
from dateutil.relativedelta import relativedelta

from odoo import api, Command, fields, models, _
from odoo.exceptions import UserError, ValidationError

SCORES = [
    ('1', '1 - Deficiente'),
    ('2', '2 - Regular'),
    ('3', '3 - Bueno'),
    ('4', '4 - Muy bueno'),
    ('5', '5 - Excelente'),
]
RATINGS = [
    ('A', 'A - Preferente'),
    ('B', 'B - Aprobado'),
    ('C', 'C - Observado'),
    ('D', 'D - No recomendado'),
]


def rating_from_score(score):
    """Nota 0-100 -> categoría A/B/C/D."""
    if score >= 85:
        return 'A'
    if score >= 70:
        return 'B'
    if score >= 50:
        return 'C'
    return 'D'


def score_from_on_time_rate(rate):
    """% de entregas a tiempo -> puntaje 1-5."""
    if rate >= 95:
        return '5'
    if rate >= 85:
        return '4'
    if rate >= 70:
        return '3'
    if rate >= 50:
        return '2'
    return '1'


class NuageVendorEvaluation(models.Model):
    _name = 'nuage.vendor.evaluation'
    _description = 'Evaluación de proveedor'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_to desc, id desc'

    def _default_lines(self):
        criteria = self.env['nuage.vendor.criterion'].search([])
        return [Command.create({'criterion_id': c.id}) for c in criteria]

    name = fields.Char('Número', default='/', readonly=True, copy=False)
    partner_id = fields.Many2one('res.partner', string='Proveedor', required=True,
                                 tracking=True, index=True)
    company_id = fields.Many2one('res.company', string='Empresa', required=True,
                                 default=lambda self: self.env.company)
    evaluator_id = fields.Many2one('res.users', string='Evaluador',
                                   default=lambda self: self.env.user)
    date_from = fields.Date('Desde', required=True,
                            default=lambda self: fields.Date.context_today(self) - relativedelta(months=3))
    date_to = fields.Date('Hasta', required=True, default=fields.Date.context_today)
    state = fields.Selection(
        [('draft', 'Borrador'), ('confirmed', 'Confirmada'), ('cancel', 'Cancelada')],
        string='Estado', default='draft', required=True, tracking=True, copy=False)
    line_ids = fields.One2many('nuage.vendor.evaluation.line', 'evaluation_id',
                               string='Criterios', copy=True, default=_default_lines)
    total_score = fields.Float('Nota final (0-100)', compute='_compute_total', store=True,
                               aggregator='avg', digits=(5, 1))
    rating = fields.Selection(RATINGS, string='Categoría', compute='_compute_total', store=True,
                              tracking=True)
    deliveries_total = fields.Integer('Recepciones del período', readonly=True, copy=False)
    deliveries_on_time = fields.Integer('Recepciones a tiempo', readonly=True, copy=False)
    on_time_rate = fields.Float('% a tiempo', compute='_compute_on_time_rate', store=True,
                                digits=(5, 1))
    notes = fields.Text('Observaciones')

    @api.depends('line_ids.score', 'line_ids.weight')
    def _compute_total(self):
        for rec in self:
            scored = rec.line_ids.filtered('score')
            weights = sum(scored.mapped('weight'))
            if scored and weights:
                points = sum(int(line.score) * line.weight for line in scored)
                rec.total_score = points / (5.0 * weights) * 100.0
                rec.rating = rating_from_score(rec.total_score)
            else:
                rec.total_score = 0.0
                rec.rating = False

    @api.depends('deliveries_total', 'deliveries_on_time')
    def _compute_on_time_rate(self):
        for rec in self:
            rec.on_time_rate = (rec.deliveries_on_time / rec.deliveries_total * 100.0
                                if rec.deliveries_total else 0.0)

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for rec in self:
            if rec.date_from > rec.date_to:
                raise ValidationError(_('La fecha "Desde" no puede ser posterior a "Hasta".'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('nuage.vendor.evaluation') or '/'
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Cálculo automático de entregas
    # ------------------------------------------------------------------
    def _get_period_bounds_utc(self):
        """Límites del período [Desde, Hasta] como datetimes UTC (naive), calculados con la misma
        zona horaria que se usa para decidir si una recepción llegó a tiempo. Así una recepción
        hecha de noche el último día del período no queda fuera por la diferencia con UTC."""
        self.ensure_one()
        tz = pytz.timezone(self.env.context.get('tz') or self.env.user.tz or 'UTC')

        def to_utc(day):
            local = tz.localize(datetime.combine(day, time.min))
            return local.astimezone(pytz.utc).replace(tzinfo=None)

        return to_utc(self.date_from), to_utc(self.date_to + timedelta(days=1))

    def action_compute_deliveries(self):
        """Cuenta las recepciones de compra del período y cuántas llegaron a tiempo
        (fecha real <= fecha prevista de la orden de compra, en la zona horaria del usuario)."""
        Picking = self.env['stock.picking']
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Solo se pueden recalcular evaluaciones en borrador.'))
            start, end = rec._get_period_bounds_utc()
            pickings = Picking.search([
                ('picking_type_code', '=', 'incoming'),
                ('state', '=', 'done'),
                ('company_id', '=', rec.company_id.id),
                ('purchase_id.partner_id.commercial_partner_id', '=',
                 rec.partner_id.commercial_partner_id.id),
                ('date_done', '>=', start),
                ('date_done', '<', end),
            ])
            if not pickings:
                raise UserError(_('No hay recepciones de compra confirmadas de este proveedor '
                                  'en el período indicado.'))
            on_time = 0
            for picking in pickings:
                planned = picking.purchase_id.date_planned or picking.scheduled_date
                done_day = fields.Date.context_today(rec, picking.date_done)
                planned_day = fields.Date.context_today(rec, planned)
                if done_day <= planned_day:
                    on_time += 1
            rec.write({'deliveries_total': len(pickings), 'deliveries_on_time': on_time})
            score = score_from_on_time_rate(rec.on_time_rate)
            rec.line_ids.filtered('is_delivery').write({'score': score})
        return True

    # ------------------------------------------------------------------
    # Flujo de estados
    # ------------------------------------------------------------------
    def action_confirm(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError(_('La evaluación no tiene criterios.'))
            missing = rec.line_ids.filtered(lambda l: not l.score)
            if missing:
                raise UserError(_('Falta calificar: %s', ', '.join(missing.mapped('criterion_id.name'))))
            rec.state = 'confirmed'

    def action_draft(self):
        # Reabrir una evaluación confirmada permite cambiar la nota: solo el jefe de Compras.
        if (any(rec.state == 'confirmed' for rec in self)
                and not self.env.user.has_group('purchase.group_purchase_manager')):
            raise UserError(_('Solo el jefe de Compras puede reabrir una evaluación confirmada.'))
        self.write({'state': 'draft'})

    def action_cancel(self):
        self.write({'state': 'cancel'})


class NuageVendorEvaluationLine(models.Model):
    _name = 'nuage.vendor.evaluation.line'
    _description = 'Línea de evaluación de proveedor'
    _order = 'sequence, id'

    evaluation_id = fields.Many2one('nuage.vendor.evaluation', required=True, ondelete='cascade',
                                    index=True)
    criterion_id = fields.Many2one('nuage.vendor.criterion', string='Criterio', required=True,
                                   ondelete='restrict')
    sequence = fields.Integer(related='criterion_id.sequence', store=True)
    is_delivery = fields.Boolean(related='criterion_id.is_delivery')
    # El peso se copia al crear la línea para que cambiar el criterio después
    # no altere evaluaciones históricas.
    weight = fields.Float('Peso (%)', readonly=True)
    score = fields.Selection(SCORES, string='Puntaje')
    notes = fields.Char('Comentario')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'weight' not in vals and vals.get('criterion_id'):
                vals['weight'] = self.env['nuage.vendor.criterion'].browse(vals['criterion_id']).weight
        return super().create(vals_list)

    _LOCKED_FIELDS = {'criterion_id', 'weight', 'score', 'notes'}

    def _check_evaluation_is_draft(self):
        if any(line.evaluation_id.state != 'draft' for line in self):
            raise UserError(_('La evaluación no está en borrador. Vuélvala a borrador para modificar '
                              'los criterios.'))

    def write(self, vals):
        if self._LOCKED_FIELDS & set(vals):
            self._check_evaluation_is_draft()
        return super().write(vals)

    def unlink(self):
        self._check_evaluation_is_draft()
        return super().unlink()
