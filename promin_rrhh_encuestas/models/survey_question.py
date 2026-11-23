# -*- coding: utf-8 -*-
from odoo import fields, models


class SurveyQuestion(models.Model):
    _inherit = 'survey.question'

    promin_bloque = fields.Selection(
        [('valores', 'Valores'), ('generales', 'Competencias generales'),
         ('especificas', 'Competencias específicas (jefes)')],
        string='Bloque de evaluación',
        help='Bloque de la evaluación de desempeño al que pertenece esta pregunta de matriz; '
             'se usa para calcular los promedios por empleado.')
    promin_segmento = fields.Selection(
        [('area', 'Área'), ('puesto', 'Puesto'), ('sexo', 'Sexo'), ('edad', 'Edad'),
         ('estudios', 'Nivel de estudios'), ('antiguedad', 'Antigüedad')],
        string='Segmento (clima)',
        help='Marca las preguntas demográficas del clima laboral para poder ver los resultados por segmento.')
    promin_es_area = fields.Boolean(
        'Opciones = departamentos',
        help='Las opciones de esta pregunta se cargan desde los departamentos de RRHH '
             '(acción «Sincronizar áreas con departamentos» en Encuestas).')
    promin_precarga = fields.Selection(
        [('evaluado', 'Nombre del evaluado'), ('evaluador', 'Nombre del jefe evaluador'),
         ('area', 'Área del evaluado')],
        string='Precarga (desempeño)',
        help='Al generar las evaluaciones, esta pregunta se rellena con el dato indicado.')
