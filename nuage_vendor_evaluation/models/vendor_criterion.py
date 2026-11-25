from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class NuageVendorCriterion(models.Model):
    _name = 'nuage.vendor.criterion'
    _description = 'Criterio de evaluación de proveedores'
    _order = 'sequence, id'

    name = fields.Char('Criterio', required=True, translate=True)
    sequence = fields.Integer('Secuencia', default=10)
    weight = fields.Float('Peso (%)', default=25.0, required=True,
                          help='Importancia relativa del criterio. Los pesos no necesitan sumar 100: '
                               'la nota final se normaliza con los criterios calificados.')
    is_delivery = fields.Boolean(
        'Cumplimiento de entregas',
        help='Si se marca, el botón "Calcular entregas a tiempo" de la evaluación '
             'califica automáticamente este criterio con las recepciones del período.')
    active = fields.Boolean(default=True)

    @api.constrains('weight')
    def _check_weight(self):
        for rec in self:
            if rec.weight <= 0:
                raise ValidationError(_('El peso de un criterio debe ser mayor que cero.'))
