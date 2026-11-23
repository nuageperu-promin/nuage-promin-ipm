# -*- coding: utf-8 -*-
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# Configuración de cada tipo de dato: etiqueta, campos que pide el portal y si el adjunto es obligatorio.
# Cada campo: (nombre, etiqueta, tipo de control, obligatorio)
TIPOS = {
    'dni': {
        'etiqueta': 'DNI del trabajador', 'plural': 'DNI del trabajador',
        'ayuda': 'Ingrese su número de DNI y adjunte la copia por ambos lados.',
        'campos': [('numero', 'N° de DNI', 'char', True)],
        'adjunto_requerido': True,
    },
    'derechohabiente': {
        'etiqueta': 'Derechohabiente', 'plural': 'DNI de derechohabientes',
        'ayuda': 'Cónyuge o conviviente, hijos y otros derechohabientes. Adjunte la copia de su DNI o partida de nacimiento.',
        'campos': [('nombre', 'Apellidos y nombres', 'char', True),
                   ('parentesco', 'Parentesco', 'parentesco', True),
                   ('numero', 'N° de DNI / documento', 'char', True),
                   ('fecha_documento', 'Fecha de nacimiento', 'date', True)],
        'adjunto_requerido': True,
    },
    'estudio': {
        'etiqueta': 'Estudio', 'plural': 'Estudios (CV)',
        'ayuda': 'Grados, títulos, diplomados y cursos. Adjunte el diploma o la constancia.',
        'campos': [('nombre', 'Grado, título o curso', 'char', True),
                   ('entidad', 'Institución', 'char', True),
                   ('fecha_inicio', 'Desde', 'date', False),
                   ('fecha_fin', 'Hasta', 'date', False)],
        'adjunto_requerido': False,
    },
    'experiencia': {
        'etiqueta': 'Experiencia laboral', 'plural': 'Experiencia laboral (CV)',
        'ayuda': 'Experiencia en otras empresas. Adjunte el certificado o constancia de trabajo si la tiene.',
        'campos': [('nombre', 'Cargo', 'char', True),
                   ('entidad', 'Empresa', 'char', True),
                   ('fecha_inicio', 'Desde', 'date', True),
                   ('fecha_fin', 'Hasta', 'date', False),
                   ('detalle', 'Funciones realizadas', 'text', False)],
        'adjunto_requerido': False,
    },
    'cul': {
        'etiqueta': 'Certificado Único Laboral (CUL)', 'plural': 'Certificado Único Laboral (CUL)',
        'ayuda': 'Adjunte su CUL vigente.',
        'campos': [('numero', 'N° de certificado (si lo tiene)', 'char', False),
                   ('fecha_documento', 'Fecha de emisión', 'date', True)],
        'adjunto_requerido': True,
    },
}
PARENTESCOS = [('conyuge', 'Cónyuge'), ('conviviente', 'Conviviente'), ('hijo', 'Hijo(a)'),
               ('padre', 'Padre'), ('madre', 'Madre'), ('otro', 'Otro')]


class PortalDato(models.Model):
    _name = 'promin.portal.dato'
    _description = 'Dato del empleado enviado desde el Portal (pendiente de aprobación de RRHH)'
    _inherit = ['mail.thread']
    _order = 'id desc'

    name = fields.Char('Resumen', compute='_compute_name', store=True)
    employee_id = fields.Many2one('hr.employee', 'Empleado', required=True, index=True, ondelete='cascade',
                                  tracking=True)
    department_id = fields.Many2one('hr.department', 'Departamento', related='employee_id.department_id', store=True)
    tipo = fields.Selection([(k, v['etiqueta']) for k, v in TIPOS.items()], 'Tipo', required=True,
                            index=True)
    state = fields.Selection(
        [('pendiente', 'Pendiente de aprobación'), ('aprobado', 'Aprobado'),
         ('rechazado', 'Rechazado'), ('reemplazado', 'Reemplazado')],
        'Estado', default='pendiente', required=True, tracking=True, index=True)
    nombre = fields.Char('Nombre / título')
    numero = fields.Char('N° de documento')
    entidad = fields.Char('Institución / empresa')
    parentesco = fields.Selection(PARENTESCOS, 'Parentesco')
    fecha_documento = fields.Date('Fecha (nacimiento / emisión)')
    fecha_inicio = fields.Date('Desde')
    fecha_fin = fields.Date('Hasta')
    detalle = fields.Text('Detalle')
    attachment_ids = fields.Many2many('ir.attachment', 'promin_portal_dato_attachment_rel', 'dato_id',
                                      'attachment_id', string='Archivos adjuntos')
    reemplaza_id = fields.Many2one('promin.portal.dato', 'Reemplaza a', copy=False,
                                   help='Dato aprobado que esta solicitud reemplazará al ser aprobada.')
    motivo_rechazo = fields.Text('Motivo del rechazo', tracking=True)
    revisado_por_id = fields.Many2one('res.users', 'Revisado por', readonly=True, copy=False)
    fecha_revision = fields.Datetime('Fecha de revisión', readonly=True, copy=False)

    @api.depends('tipo', 'nombre', 'numero', 'entidad', 'employee_id')
    def _compute_name(self):
        etiquetas = dict(self._fields['tipo'].selection)
        for dato in self:
            detalle = ' - '.join(x for x in (dato.nombre, dato.entidad, dato.numero) if x)
            dato.name = '%s: %s' % (etiquetas.get(dato.tipo, ''), detalle or dato.employee_id.name or '')

    @api.constrains('tipo', 'numero')
    def _check_dni(self):
        for dato in self.filtered(lambda d: d.tipo == 'dni'):
            if not re.fullmatch(r'\d{8}', (dato.numero or '').strip()):
                raise ValidationError(_('El DNI debe tener 8 dígitos.'))

    # --- Revisión de RRHH ---
    def action_aprobar(self):
        for dato in self:
            if dato.state != 'pendiente':
                raise UserError(_('Solo se pueden aprobar los datos pendientes.'))
            if dato.reemplaza_id:
                dato.reemplaza_id.sudo().state = 'reemplazado'
            if dato.tipo == 'dni':
                dato.employee_id.sudo().identification_id = (dato.numero or '').strip()
            dato.write({'state': 'aprobado', 'motivo_rechazo': False,
                        'revisado_por_id': self.env.user.id, 'fecha_revision': fields.Datetime.now()})
        return True

    def action_rechazar(self):
        for dato in self:
            if dato.state != 'pendiente':
                raise UserError(_('Solo se pueden rechazar los datos pendientes.'))
            if not (dato.motivo_rechazo or '').strip():
                raise UserError(_('Escriba el motivo del rechazo para que el empleado lo vea en el portal.'))
            dato.write({'state': 'rechazado', 'revisado_por_id': self.env.user.id,
                        'fecha_revision': fields.Datetime.now()})
        return True
