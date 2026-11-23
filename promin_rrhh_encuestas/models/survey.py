# -*- coding: utf-8 -*-
from odoo import fields, models


class Survey(models.Model):
    _inherit = 'survey.survey'

    promin_tipo = fields.Selection(
        [('clima', 'Clima laboral'), ('desempeno', 'Evaluación de desempeño')],
        string='Tipo RRHH (PROMIN)', index=True,
        help='Marca las encuestas de RRHH de PROMIN: el clima es anónimo y la evaluación de desempeño '
             'se responde por invitación, una por cada empleado evaluado.')

    def promin_sync_areas(self):
        """Carga como opciones de las preguntas «Área» los departamentos de RRHH (no borra opciones usadas)."""
        Answer = self.env['survey.question.answer']
        departamentos = self.env['hr.department'].search([('company_id', 'in', [False] + self.env.companies.ids)])
        for survey in self:
            for pregunta in survey.question_ids.filtered('promin_es_area'):
                existentes = set(pregunta.suggested_answer_ids.mapped('value'))
                secuencia = max(pregunta.suggested_answer_ids.mapped('sequence') or [0])
                for dep in departamentos.sorted('name'):
                    nombre = dep.name
                    if nombre in existentes:
                        continue
                    secuencia += 1
                    Answer.create({'question_id': pregunta.id, 'value': nombre, 'sequence': secuencia})
                    existentes.add(nombre)
        return True
