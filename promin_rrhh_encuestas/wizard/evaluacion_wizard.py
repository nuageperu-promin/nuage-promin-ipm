# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class EvaluacionWizard(models.TransientModel):
    _name = 'promin.evaluacion.wizard'
    _description = 'Generar evaluaciones de desempeño'

    survey_id = fields.Many2one(
        'survey.survey', 'Evaluación', required=True,
        domain=[('promin_tipo', '=', 'desempeno')])
    department_ids = fields.Many2many('hr.department', string='Áreas')
    employee_ids = fields.Many2many(
        'hr.employee', string='Empleados a evaluar',
        help='Vacío = todos los empleados activos (de las áreas elegidas, si se indican) que tengan jefe.')
    enviar_correo = fields.Boolean('Enviar enlace por correo al jefe', default=True)
    state = fields.Selection([('config', 'Configuración'), ('done', 'Resultado')], default='config')
    resultado = fields.Text('Resultado', readonly=True)

    def action_generar(self):
        self.ensure_one()
        survey = self.survey_id
        empleados = self.employee_ids
        if not empleados:
            dominio = [('active', '=', True)]
            if self.department_ids:
                dominio.append(('department_id', 'child_of', self.department_ids.ids))
            empleados = self.env['hr.employee'].search(dominio)
        UserInput = self.env['survey.user_input'].sudo()
        Line = self.env['survey.user_input.line'].sudo()
        preguntas = survey.question_ids.filtered('promin_precarga')
        creadas = UserInput
        existentes, sin_jefe = [], []
        for emp in empleados:
            jefe = emp.parent_id
            if not jefe or jefe == emp:
                sin_jefe.append(emp.name)
                continue
            ya = UserInput.search_count([
                ('survey_id', '=', survey.id), ('promin_empleado_id', '=', emp.id),
                ('promin_evaluador_id', '=', jefe.id)])
            if ya:
                existentes.append(emp.name)
                continue
            entrada = UserInput.create({
                'survey_id': survey.id,
                'email': jefe.work_email or jefe.user_id.email or False,
                'promin_empleado_id': emp.id,
                'promin_evaluador_id': jefe.id,
            })
            for pregunta in preguntas:
                valor = {'evaluado': emp.name, 'evaluador': jefe.name,
                         'area': emp.department_id.name}.get(pregunta.promin_precarga) or ''
                Line.create({
                    'user_input_id': entrada.id, 'question_id': pregunta.id,
                    'answer_type': 'char_box', 'value_char_box': valor, 'skipped': False,
                })
            creadas |= entrada
        lineas = [_('Evaluaciones generadas: %s.', len(creadas))]
        if self.enviar_correo and creadas:
            enviados, sin_correo = creadas._promin_enviar_enlace()
            lineas.append(_('Enlaces enviados por correo: %s.', enviados))
            if sin_correo:
                lineas.append(_('Jefes sin correo (envíe el enlace desde la lista): %s.', ', '.join(sin_correo)))
        if existentes:
            lineas.append(_('Ya existían (no se duplicaron): %s.', ', '.join(existentes)))
        if sin_jefe:
            lineas.append(_('Sin jefe asignado en su ficha (no se generó): %s.', ', '.join(sin_jefe)))
        if not empleados:
            raise UserError(_('No hay empleados para evaluar con ese filtro.'))
        self.write({'state': 'done', 'resultado': '\n'.join(lineas)})
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
                'view_mode': 'form', 'target': 'new'}

    def action_ver_evaluaciones(self):
        self.ensure_one()
        return self.env['ir.actions.act_window']._for_xml_id(
            'promin_rrhh_encuestas.action_promin_desempeno_resultados')
