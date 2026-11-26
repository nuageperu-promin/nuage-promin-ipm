# -*- coding: utf-8 -*-
import base64
import logging
import os

from odoo import _, fields, http
from odoo.exceptions import AccessError, UserError
from odoo.http import request

from ..models.dato import PARENTESCOS, TIPOS

_logger = logging.getLogger(__name__)

EXT_PERMITIDAS = {'.pdf', '.jpg', '.jpeg', '.png'}
MAX_BYTES = 5 * 1024 * 1024
MAX_ARCHIVOS = 5


class PortalEmpleado(http.Controller):

    # ------------------------------------------------------------ utilidades
    def _empleado(self):
        emp = request.env['hr.employee'].sudo().search(
            [('promin_portal_user_id', '=', request.env.user.id)], limit=1)
        if not emp:
            raise AccessError(_('Su usuario no está vinculado a un empleado.'))
        return emp

    def _dato_propio(self, dato_id):
        dato = request.env['promin.portal.dato'].sudo().browse(dato_id).exists()
        if not dato or dato.employee_id != self._empleado():
            raise AccessError(_('No tiene acceso a este dato.'))
        return dato

    def _render(self, template, valores):
        valores.setdefault('empleado', self._empleado())
        return request.render('promin_portal_empleado.' + template, valores)

    def _valores_form(self, tipo, post):
        """Toma del POST los campos del tipo indicado. Devuelve (valores, errores)."""
        valores, errores = {}, []
        for campo, etiqueta, control, obligatorio in TIPOS[tipo]['campos']:
            bruto = (post.get(campo) or '').strip()
            if not bruto:
                if obligatorio:
                    errores.append(_('Complete el campo «%s».', etiqueta))
                valores[campo] = False
                continue
            if control == 'date':
                try:
                    valores[campo] = fields.Date.to_date(bruto)
                except Exception:
                    errores.append(_('Fecha no válida en «%s».', etiqueta))
                    continue
            elif control == 'parentesco':
                if bruto not in dict(PARENTESCOS):
                    errores.append(_('Elija un parentesco válido.'))
                    continue
                valores[campo] = bruto
            else:
                valores[campo] = bruto
        if valores.get('fecha_inicio') and valores.get('fecha_fin') and valores['fecha_inicio'] > valores['fecha_fin']:
            errores.append(_('La fecha «Desde» no puede ser posterior a «Hasta».'))
        return valores, errores

    def _crear_adjuntos(self, dato, archivos):
        """Valida y guarda los archivos subidos. Devuelve (ids, errores)."""
        ids, errores = [], []
        archivos = [a for a in archivos if a and a.filename]
        if len(archivos) > MAX_ARCHIVOS:
            errores.append(_('Máximo %s archivos por envío.', MAX_ARCHIVOS))
            return ids, errores
        for archivo in archivos:
            ext = os.path.splitext(archivo.filename)[1].lower()
            contenido = archivo.read()
            if ext not in EXT_PERMITIDAS:
                errores.append(_('«%s»: solo se permiten PDF, JPG o PNG.', archivo.filename))
            elif len(contenido) > MAX_BYTES:
                errores.append(_('«%s»: supera los 5 MB.', archivo.filename))
            elif not contenido:
                errores.append(_('«%s» está vacío.', archivo.filename))
            else:
                att = request.env['ir.attachment'].sudo().create({
                    'name': archivo.filename, 'datas': base64.b64encode(contenido),
                    'res_model': dato._name, 'res_id': dato.id, 'public': False})
                ids.append(att.id)
        return ids, errores

    # ------------------------------------------------------------ páginas
    @http.route('/my/empleado/datos', type='http', auth='user', website=True)
    def datos(self, **kw):
        emp = self._empleado()
        datos = request.env['promin.portal.dato'].sudo().search(
            [('employee_id', '=', emp.id), ('state', '!=', 'reemplazado')])
        por_tipo = {t: datos.filtered(lambda d, t=t: d.tipo == t) for t in TIPOS}
        return self._render('portal_datos', {
            'tipos': TIPOS, 'por_tipo': por_tipo, 'parentescos': dict(PARENTESCOS),
            'aviso': kw.get('aviso')})

    @http.route('/my/empleado/datos/nuevo/<string:tipo>', type='http', auth='user', website=True, methods=['GET', 'POST'],
                csrf=True)
    def nuevo(self, tipo, **post):
        if tipo not in TIPOS:
            return request.redirect('/my/empleado/datos')
        return self._formulario(tipo, None, post)

    @http.route('/my/empleado/datos/<int:dato_id>/editar', type='http', auth='user', website=True, methods=['GET', 'POST'],
                csrf=True)
    def editar(self, dato_id, **post):
        dato = self._dato_propio(dato_id)
        if dato.state not in ('pendiente', 'rechazado'):
            return request.redirect('/my/empleado/datos')
        return self._formulario(dato.tipo, dato, post)

    @http.route('/my/empleado/datos/<int:dato_id>/cambio', type='http', auth='user', website=True, methods=['GET', 'POST'],
                csrf=True)
    def cambio(self, dato_id, **post):
        """Solicitud de cambio sobre un dato ya aprobado: crea uno nuevo que lo reemplaza al aprobarse."""
        dato = self._dato_propio(dato_id)
        if dato.state != 'aprobado':
            return request.redirect('/my/empleado/datos')
        return self._formulario(dato.tipo, None, post, reemplaza=dato)

    def _formulario(self, tipo, dato, post, reemplaza=None):
        emp = self._empleado()
        config = TIPOS[tipo]
        errores = []
        origen = dato or reemplaza
        valores = {c[0]: (origen[c[0]] if origen else '') for c in config['campos']}
        if request.httprequest.method == 'POST':
            valores, errores = self._valores_form(tipo, post)
            archivos = request.httprequest.files.getlist('adjuntos')
            hay_archivos = any(a and a.filename for a in archivos)
            tiene_previos = bool(dato and dato.attachment_ids)
            if config['adjunto_requerido'] and not hay_archivos and not tiene_previos:
                errores.append(_('Adjunte el archivo requerido (PDF, JPG o PNG, máx. 5 MB).'))
            if not errores:
                Dato = request.env['promin.portal.dato'].sudo()
                if dato:
                    dato.write(dict(valores, state='pendiente', motivo_rechazo=False))
                    registro = dato
                else:
                    registro = Dato.create(dict(valores, employee_id=emp.id, tipo=tipo,
                                                reemplaza_id=reemplaza.id if reemplaza else False))
                ids, errores_arch = self._crear_adjuntos(registro, archivos)
                if errores_arch:
                    errores = errores_arch
                    if not dato:
                        registro.unlink()
                else:
                    if ids:
                        registro.write({'attachment_ids': [(4, i) for i in ids]})
                    return request.redirect('/my/empleado/datos?aviso=enviado')
        return self._render('portal_datos_form', {
            'tipo': tipo, 'config': config, 'dato': dato, 'reemplaza': reemplaza, 'valores': valores,
            'errores': errores, 'parentescos': PARENTESCOS,
            'max_mb': MAX_BYTES // (1024 * 1024), 'max_archivos': MAX_ARCHIVOS})

    @http.route('/my/empleado/datos/<int:dato_id>/eliminar', type='http', auth='user', website=True, methods=['POST'],
                csrf=True)
    def eliminar(self, dato_id, **post):
        dato = self._dato_propio(dato_id)
        if dato.state in ('pendiente', 'rechazado'):
            dato.attachment_ids.sudo().unlink()
            dato.unlink()
        return request.redirect('/my/empleado/datos')

    @http.route('/my/empleado/archivo/<int:dato_id>/<int:att_id>', type='http', auth='user', website=True)
    def archivo_dato(self, dato_id, att_id, **kw):
        dato = self._dato_propio(dato_id)
        att = dato.attachment_ids.filtered(lambda a: a.id == att_id)
        if not att:
            raise AccessError(_('Archivo no disponible.'))
        return request.make_response(base64.b64decode(att.datas), headers=[
            ('Content-Type', att.mimetype or 'application/octet-stream'),
            ('Content-Disposition', 'inline; filename="%s"' % att.name.replace('"', ''))])

    @http.route('/my/empleado/documentos', type='http', auth='user', website=True)
    def documentos(self, **kw):
        emp = self._empleado()
        docs = request.env['promin.portal.documento'].sudo().search(
            [('employee_id', '=', emp.id), ('publicado', '=', True)])
        boletas = request.env['hr.payslip'].sudo().search(
            [('employee_id', '=', emp.id), ('state', 'in', ('validated', 'paid'))],
            order='date_from desc')
        return self._render('portal_documentos', {'documentos': docs, 'boletas': boletas})

    @http.route('/my/empleado/documento/<int:doc_id>', type='http', auth='user', website=True)
    def documento(self, doc_id, **kw):
        emp = self._empleado()
        doc = request.env['promin.portal.documento'].sudo().browse(doc_id).exists()
        if not doc or doc.employee_id != emp or not doc.publicado:
            raise AccessError(_('Documento no disponible.'))
        doc.write({'lecturas': doc.lecturas + 1,
                   'primera_lectura': doc.primera_lectura or fields.Datetime.now()})
        nombre = (doc.archivo_nombre or doc.name or 'documento').replace('"', '')
        return request.make_response(base64.b64decode(doc.archivo), headers=[
            ('Content-Type', 'application/pdf' if nombre.lower().endswith('.pdf') else 'application/octet-stream'),
            ('Content-Disposition', 'inline; filename="%s"' % nombre)])

    @http.route('/my/empleado/boleta/<int:slip_id>', type='http', auth='user', website=True)
    def boleta(self, slip_id, **kw):
        emp = self._empleado()
        slip = request.env['hr.payslip'].sudo().browse(slip_id).exists()
        if not slip or slip.employee_id != emp or slip.state not in ('validated', 'paid'):
            raise AccessError(_('Boleta no disponible.'))
        reporte = request.env.ref('solse_pe_payroll.action_reporte_boleta_pago', raise_if_not_found=False) \
            or request.env.ref('hr_payroll.action_report_payslip')
        pdf, _tipo = reporte.sudo()._render_qweb_pdf(reporte.report_name, [slip.id])
        slip._promin_registrar_lectura()
        nombre = 'Boleta_%s.pdf' % (slip.date_from or slip.id)
        return request.make_response(pdf, headers=[
            ('Content-Type', 'application/pdf'),
            ('Content-Disposition', 'inline; filename="%s"' % nombre)])
