# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

SEGMENTOS = ('area', 'puesto', 'sexo', 'edad', 'estudios', 'antiguedad')


class SurveyUserInput(models.Model):
    _inherit = 'survey.user_input'

    # --- Evaluación de desempeño ---
    promin_empleado_id = fields.Many2one(
        'hr.employee', 'Empleado evaluado', index=True, ondelete='set null')
    promin_evaluador_id = fields.Many2one(
        'hr.employee', 'Jefe evaluador', index=True, ondelete='set null')
    promin_departamento_id = fields.Many2one(
        'hr.department', 'Área del evaluado', related='promin_empleado_id.department_id', store=True)
    promin_prom_valores = fields.Float(
        'Prom. Valores', compute='_compute_promin_promedios', store=True, aggregator='avg')
    promin_prom_generales = fields.Float(
        'Prom. Comp. generales', compute='_compute_promin_promedios', store=True, aggregator='avg')
    promin_prom_especificas = fields.Float(
        'Prom. Comp. específicas', compute='_compute_promin_promedios', store=True, aggregator='avg')
    promin_prom_total = fields.Float(
        'Promedio total', compute='_compute_promin_promedios', store=True, aggregator='avg',
        help='Promedio de todos los ítems calificados (valores + competencias generales + específicas).')

    # --- Clima laboral: segmento tomado de las respuestas demográficas ---
    promin_seg_area = fields.Char('Área', compute='_compute_promin_segmentos', store=True)
    promin_seg_puesto = fields.Char('Puesto', compute='_compute_promin_segmentos', store=True)
    promin_seg_sexo = fields.Char('Sexo', compute='_compute_promin_segmentos', store=True)
    promin_seg_edad = fields.Char('Edad', compute='_compute_promin_segmentos', store=True)
    promin_seg_estudios = fields.Char('Nivel de estudios', compute='_compute_promin_segmentos', store=True)
    promin_seg_antiguedad = fields.Char('Antigüedad', compute='_compute_promin_segmentos', store=True)

    @api.depends('user_input_line_ids.suggested_answer_id', 'user_input_line_ids.question_id',
                 'user_input_line_ids.skipped')
    def _compute_promin_promedios(self):
        for entrada in self:
            notas = {'valores': [], 'generales': [], 'especificas': []}
            for linea in entrada.user_input_line_ids:
                bloque = linea.question_id.promin_bloque
                if bloque and linea.answer_type == 'suggestion' and not linea.skipped \
                        and linea.suggested_answer_id:
                    notas[bloque].append(linea.suggested_answer_id.answer_score)
            todas = [n for lista in notas.values() for n in lista]

            def promedio(lista):
                return sum(lista) / len(lista) if lista else 0.0

            entrada.promin_prom_valores = promedio(notas['valores'])
            entrada.promin_prom_generales = promedio(notas['generales'])
            entrada.promin_prom_especificas = promedio(notas['especificas'])
            entrada.promin_prom_total = promedio(todas)

    @api.depends('user_input_line_ids.suggested_answer_id', 'user_input_line_ids.question_id')
    def _compute_promin_segmentos(self):
        for entrada in self:
            valores = dict.fromkeys(SEGMENTOS, False)
            for linea in entrada.user_input_line_ids:
                segmento = linea.question_id.promin_segmento
                if segmento and linea.suggested_answer_id:
                    valores[segmento] = linea.suggested_answer_id.value
            for segmento in SEGMENTOS:
                entrada['promin_seg_' + segmento] = valores[segmento]

    # --- Enlace de evaluación ---
    def _promin_url_evaluacion(self):
        self.ensure_one()
        survey = self.survey_id
        return '%s/survey/start/%s?answer_token=%s' % (
            survey.get_base_url(), survey.access_token, self.access_token)

    def _promin_enviar_enlace(self):
        """Envía por correo al jefe evaluador el enlace de cada evaluación pendiente. Devuelve (enviados, sin_correo)."""
        enviados, sin_correo = 0, []
        for entrada in self.filtered(lambda e: e.state != 'done' and e.promin_empleado_id):
            jefe = entrada.promin_evaluador_id
            destino = entrada.email or jefe.work_email or jefe.user_id.email
            if not destino:
                sin_correo.append(jefe.name or entrada.promin_empleado_id.name)
                continue
            cuerpo = _(
                '<p>Estimado(a) %(jefe)s:</p>'
                '<p>Le solicitamos completar la <b>%(encuesta)s</b> de <b>%(evaluado)s</b>.</p>'
                '<p><a href="%(url)s">Completar evaluación</a></p>'
                '<p>El enlace es personal. Gracias.</p>',
                jefe=jefe.name or '', encuesta=entrada.survey_id.title,
                evaluado=entrada.promin_empleado_id.name, url=entrada._promin_url_evaluacion())
            self.env['mail.mail'].sudo().create({
                'subject': _('%(encuesta)s: %(evaluado)s', encuesta=entrada.survey_id.title,
                             evaluado=entrada.promin_empleado_id.name),
                'body_html': cuerpo, 'email_to': destino, 'auto_delete': True,
            }).send()
            enviados += 1
        return enviados, sin_correo

    def action_promin_enviar_enlace(self):
        enviados, sin_correo = self._promin_enviar_enlace()
        if not enviados and not sin_correo:
            raise UserError(_('No hay evaluaciones pendientes entre los registros seleccionados.'))
        mensaje = _('Enlaces enviados: %s.', enviados)
        if sin_correo:
            mensaje += ' ' + _('Sin correo del evaluador: %s.', ', '.join(sin_correo))
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': _('Evaluaciones de desempeño'), 'message': mensaje,
                           'type': 'warning' if sin_correo else 'success', 'sticky': bool(sin_correo)}}

    def action_promin_abrir_evaluacion(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_url', 'url': self._promin_url_evaluacion(), 'target': 'new'}
