# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SurveyUserInputLine(models.Model):
    _inherit = 'survey.user_input.line'

    promin_valor = fields.Float(
        'Calificación (1-5)', compute='_compute_promin_valor', store=True, aggregator='avg',
        help='Valor numérico de la opción elegida en las preguntas de matriz (1 a 5).')
    promin_seg_area = fields.Char('Área', related='user_input_id.promin_seg_area', store=True)
    promin_seg_puesto = fields.Char('Puesto', related='user_input_id.promin_seg_puesto', store=True)
    promin_seg_sexo = fields.Char('Sexo', related='user_input_id.promin_seg_sexo', store=True)
    promin_seg_edad = fields.Char('Edad', related='user_input_id.promin_seg_edad', store=True)
    promin_seg_estudios = fields.Char(
        'Nivel de estudios', related='user_input_id.promin_seg_estudios', store=True)
    promin_seg_antiguedad = fields.Char(
        'Antigüedad', related='user_input_id.promin_seg_antiguedad', store=True)
    promin_empleado_id = fields.Many2one(
        'hr.employee', 'Empleado evaluado', related='user_input_id.promin_empleado_id', store=True)
    promin_departamento_id = fields.Many2one(
        'hr.department', 'Área del evaluado', related='user_input_id.promin_departamento_id', store=True)

    @api.depends('suggested_answer_id.answer_score', 'answer_type', 'skipped', 'question_id.question_type')
    def _compute_promin_valor(self):
        for linea in self:
            if linea.answer_type == 'suggestion' and not linea.skipped and linea.suggested_answer_id \
                    and linea.question_id.question_type == 'matrix':
                linea.promin_valor = linea.suggested_answer_id.answer_score
            else:
                linea.promin_valor = 0.0
