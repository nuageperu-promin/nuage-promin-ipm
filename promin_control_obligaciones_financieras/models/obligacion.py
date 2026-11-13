# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

TIPOS = [
    ('pagare', 'Pagaré / préstamo'),
    ('carta_fianza', 'Carta fianza'),
    ('leasing', 'Leasing'),
    ('descuento', 'Descuento de facturas / factoring'),
    ('otro', 'Otra obligación'),
]

# Prefijo de cuenta de pasivo por tipo (sufijo 1 = soles, 2 = dólares).
CUENTA_PASIVO = {
    'pagare': '454400',
    'leasing': '452000',
    'descuento': '454900',
    'otro': '454900',
}

G_FINANZAS = 'promin_control_obligaciones_financieras.group_obl_finanzas'
G_TESORERIA = 'promin_control_obligaciones_financieras.group_obl_tesoreria'
G_CONTABILIDAD = 'promin_control_obligaciones_financieras.group_obl_contabilidad'


class Obligacion(models.Model):
    _name = 'promin.obligacion'
    _description = 'Obligación financiera'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'fecha_desembolso desc, id desc'

    name = fields.Char(string='Número', default='Nuevo', copy=False, readonly=True, tracking=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True,
                                 default=lambda self: self.env.company)
    tipo = fields.Selection(TIPOS, string='Tipo', required=True, default='pagare', tracking=True)
    banco_id = fields.Many2one('res.partner', string='Banco / entidad', required=True, tracking=True)
    nro_operacion = fields.Char(string='N° de operación / pagaré', required=True, tracking=True)
    finalidad = fields.Char(string='Finalidad', help='Ej.: capital de trabajo, importación.')
    garantia = fields.Char(string='Garantía')
    linea_id = fields.Many2one('promin.obligacion.linea', string='Línea de crédito')
    currency_id = fields.Many2one('res.currency', string='Moneda', required=True, tracking=True,
                                  default=lambda self: self.env.company.currency_id)
    monto = fields.Monetary(string='Monto', currency_field='currency_id', required=True, tracking=True)
    tea = fields.Float(string='TEA (%)', digits=(16, 4), tracking=True,
                       help='Tasa efectiva anual. En cartas fianza es la tasa de comisión (referencial).')
    fecha_desembolso = fields.Date(string='Fecha de desembolso', required=True, tracking=True,
                                   default=fields.Date.context_today)
    fecha_vencimiento = fields.Date(string='Fecha de vencimiento', required=True, tracking=True)
    plazo_dias = fields.Integer(string='Plazo (días)', compute='_compute_plazo_dias')
    factura_ids = fields.Many2many(
        'account.move', 'promin_obligacion_factura_rel', 'obligacion_id', 'move_id',
        string='Facturas de proveedor financiadas', domain="[('move_type', '=', 'in_invoice')]")
    diario_banco_id = fields.Many2one(
        'account.journal', string='Diario del banco', domain="[('type', '=', 'bank')]",
        help='Cuenta bancaria donde se abona el desembolso y desde donde se pagan las cuotas.')
    cuenta_pasivo_id = fields.Many2one(
        'account.account', string='Cuenta del pasivo',
        help='Ej.: 4544001 Pagarés MN / 4544002 Pagarés ME.')
    responsable_id = fields.Many2one('res.users', string='Responsable de alertas',
                                     default=lambda self: self.env.user, tracking=True)
    state = fields.Selection([
        ('borrador', 'Borrador'), ('aprobado', 'Aprobado'), ('vigente', 'Vigente'),
        ('cancelado', 'Cancelado'), ('anulado', 'Anulado')],
        string='Estado', default='borrador', required=True, tracking=True, copy=False)
    cuota_ids = fields.One2many('promin.obligacion.cuota', 'obligacion_id', string='Cuotas', copy=False)
    move_ids = fields.One2many('account.move', 'promin_obligacion_id', string='Asientos')
    move_count = fields.Integer(string='N° de asientos', compute='_compute_move_count')
    move_desembolso_id = fields.Many2one('account.move', string='Asiento de desembolso',
                                         readonly=True, copy=False)
    saldo_capital = fields.Monetary(string='Saldo de capital', currency_field='currency_id',
                                    compute='_compute_saldo_capital', store=True)
    saldo_corriente = fields.Monetary(string='Parte corriente', currency_field='currency_id',
                                      compute='_compute_corriente')
    saldo_no_corriente = fields.Monetary(string='Parte no corriente', currency_field='currency_id',
                                         compute='_compute_corriente')
    interes_pendiente = fields.Monetary(string='Intereses por pagar', currency_field='currency_id',
                                        compute='_compute_interes')
    interes_pagado = fields.Monetary(string='Intereses pagados', currency_field='currency_id',
                                     compute='_compute_interes')
    proximo_vencimiento = fields.Date(string='Próximo vencimiento', compute='_compute_proximo', store=True)
    notas = fields.Html(string='Notas')

    # ------------------------------------------------------------------ cómputos
    @api.depends('fecha_desembolso', 'fecha_vencimiento')
    def _compute_plazo_dias(self):
        for rec in self:
            if rec.fecha_desembolso and rec.fecha_vencimiento:
                rec.plazo_dias = (rec.fecha_vencimiento - rec.fecha_desembolso).days
            else:
                rec.plazo_dias = 0

    def _compute_move_count(self):
        for rec in self:
            rec.move_count = len(rec.move_ids)

    @api.depends('tipo', 'state', 'monto', 'cuota_ids.estado', 'cuota_ids.capital_pagado')
    def _compute_saldo_capital(self):
        for rec in self:
            if rec.state != 'vigente':
                rec.saldo_capital = 0.0
            elif rec.tipo == 'carta_fianza':
                rec.saldo_capital = rec.monto
            else:
                pagado = sum(rec.cuota_ids.filtered(lambda c: c.estado == 'pagada').mapped('capital_pagado'))
                rec.saldo_capital = max(rec.monto - pagado, 0.0)

    def _compute_corriente(self):
        """Primeras 12 cuotas por vencer = parte corriente; el resto, no corriente."""
        for rec in self:
            if rec.state != 'vigente':
                rec.saldo_corriente = rec.saldo_no_corriente = 0.0
                continue
            pendientes = rec.cuota_ids.filtered(lambda c: c.estado == 'pendiente').sorted(
                key=lambda c: (c.fecha, c.numero))
            if rec.tipo == 'carta_fianza' or not pendientes:
                rec.saldo_corriente = rec.saldo_capital
                rec.saldo_no_corriente = 0.0
                continue
            corriente = sum(pendientes[:12].mapped('capital'))
            rec.saldo_corriente = min(corriente, rec.saldo_capital)
            rec.saldo_no_corriente = max(rec.saldo_capital - rec.saldo_corriente, 0.0)

    def _compute_interes(self):
        for rec in self:
            rec.interes_pendiente = sum(rec.cuota_ids.filtered(lambda c: c.estado == 'pendiente').mapped('interes'))
            rec.interes_pagado = sum(rec.cuota_ids.filtered(lambda c: c.estado == 'pagada').mapped('interes_pagado'))

    @api.depends('state', 'fecha_vencimiento', 'cuota_ids.fecha', 'cuota_ids.estado')
    def _compute_proximo(self):
        for rec in self:
            pendientes = rec.cuota_ids.filtered(lambda c: c.estado == 'pendiente')
            if rec.state == 'vigente' and pendientes:
                rec.proximo_vencimiento = min(pendientes.mapped('fecha'))
            elif rec.state in ('vigente', 'aprobado', 'borrador'):
                rec.proximo_vencimiento = rec.fecha_vencimiento
            else:
                rec.proximo_vencimiento = False

    # ---------------------------------------------------------------- validaciones
    @api.constrains('monto', 'fecha_desembolso', 'fecha_vencimiento')
    def _check_valores(self):
        for rec in self:
            if rec.monto <= 0:
                raise ValidationError(_('El monto debe ser mayor a cero.'))
            if rec.fecha_vencimiento and rec.fecha_desembolso and rec.fecha_vencimiento < rec.fecha_desembolso:
                raise ValidationError(_('La fecha de vencimiento no puede ser anterior al desembolso.'))

    @api.constrains('nro_operacion', 'banco_id', 'company_id')
    def _check_unico(self):
        for rec in self:
            dup = self.search_count([
                ('id', '!=', rec.id), ('company_id', '=', rec.company_id.id),
                ('banco_id', '=', rec.banco_id.id), ('nro_operacion', '=', rec.nro_operacion),
                ('state', '!=', 'anulado')])
            if dup and rec.state != 'anulado':
                raise ValidationError(_('Ya existe una obligación del mismo banco con el N° de operación %s.')
                                      % rec.nro_operacion)

    @api.onchange('tipo', 'currency_id', 'company_id')
    def _onchange_cuenta_pasivo(self):
        for rec in self:
            rec.cuenta_pasivo_id = rec._cuenta_pasivo_defecto()

    def _cuenta_pasivo_defecto(self):
        self.ensure_one()
        prefijo = CUENTA_PASIVO.get(self.tipo)
        if not prefijo or not self.currency_id:
            return False
        sufijo = '1' if self.currency_id == self.company_id.currency_id else '2'
        Cuenta = self.env['account.account']
        cuenta = Cuenta.search([('code', '=like', prefijo + sufijo + '%')], order='code', limit=1)
        # Respaldo: plan con la cuenta general (ej. 4544) sin subcuentas por moneda.
        return cuenta or Cuenta.search([('code', '=', prefijo[:4])], limit=1)

    # -------------------------------------------------------------------- CRUD
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nuevo') in (False, 'Nuevo'):
                vals['name'] = self.env['ir.sequence'].next_by_code('promin.obligacion') or 'Nuevo'
        return super().create(vals_list)

    def unlink(self):
        if any(rec.state not in ('borrador', 'anulado') for rec in self):
            raise UserError(_('Solo se pueden eliminar obligaciones en borrador o anuladas.'))
        return super().unlink()

    # ------------------------------------------------------------------ acciones
    def _exigir_grupo(self, xmlid, mensaje):
        if not self.env.user.has_group(xmlid) and not self.env.is_superuser():
            raise AccessError(mensaje)

    def action_aprobar(self):
        self._exigir_grupo(G_FINANZAS, _('Solo el Jefe de Finanzas puede aprobar una obligación.'))
        for rec in self:
            if rec.state != 'borrador':
                continue
            if rec.tipo != 'carta_fianza':
                if not rec.cuota_ids:
                    rec.env['promin.obligacion.cuota'].create({
                        'obligacion_id': rec.id, 'numero': 1, 'fecha': rec.fecha_vencimiento,
                        'capital': rec.monto})
                    rec.action_calcular_intereses()
                capital = sum(rec.cuota_ids.mapped('capital'))
                if abs(capital - rec.monto) > 0.009:
                    raise UserError(_(
                        'El capital del cronograma (%(cap).2f) no coincide con el monto de la obligación '
                        '(%(monto).2f). Corrija las cuotas antes de aprobar.', cap=capital, monto=rec.monto))
            if rec.linea_id:
                disponible = rec.linea_id.disponible
                monto_linea = rec.currency_id._convert(
                    rec.monto, rec.linea_id.currency_id, rec.company_id, rec.fecha_desembolso)
                if monto_linea > disponible:
                    rec.message_post(body=_(
                        'Atención: el monto supera el disponible de la línea %(linea)s (disponible %(disp).2f).',
                        linea=rec.linea_id.display_name, disp=disponible))
            rec.state = 'aprobado'
            rec.message_post(body=_('Obligación aprobada por %s.') % self.env.user.name)

    def action_borrador(self):
        for rec in self:
            if rec.state == 'aprobado':
                rec.state = 'borrador'

    def action_anular(self):
        for rec in self:
            if rec.state not in ('borrador', 'aprobado'):
                raise UserError(_('Una obligación vigente no se anula: revierta sus asientos y cancélela.'))
            rec.state = 'anulado'

    def action_desembolsar(self):
        self._exigir_grupo(G_CONTABILIDAD, _('Solo Contabilidad puede registrar el desembolso.'))
        for rec in self:
            if rec.state != 'aprobado':
                raise UserError(_('Solo se puede registrar el desembolso de una obligación aprobada.'))
            if rec.tipo != 'carta_fianza':
                rec._validar_contabilidad()
                banco = rec.diario_banco_id.default_account_id
                nombre = _('Desembolso %s') % rec.nro_operacion
                move = rec._crear_asiento(rec.fecha_desembolso, [
                    (banco, rec.monto, nombre, False),
                    (rec.cuenta_pasivo_id, -rec.monto, nombre, rec.banco_id),
                ], ref=nombre)
                rec.move_desembolso_id = move
            rec.state = 'vigente'
            rec.message_post(body=_('Desembolso registrado.'))

    def action_cancelar(self):
        for rec in self:
            if rec.state != 'vigente':
                continue
            pendientes = rec.cuota_ids.filtered(lambda c: c.estado == 'pendiente')
            if pendientes and rec.tipo != 'carta_fianza':
                raise UserError(_('Hay cuotas pendientes de pago. Regístrelas antes de cancelar.'))
            rec.state = 'cancelado'
            rec.message_post(body=_('Obligación cancelada / liberada.'))

    def action_calcular_intereses(self):
        """Rellena el interés de las cuotas pendientes sin interés: saldo × ((1+TEA)^(días/360) − 1)."""
        for rec in self:
            if rec.tipo == 'carta_fianza' or not rec.tea:
                continue
            saldo = rec.monto
            previa = rec.fecha_desembolso
            for cuota in rec.cuota_ids.sorted(key=lambda c: (c.fecha, c.numero)):
                if cuota.estado == 'pendiente' and not cuota.interes:
                    dias = (cuota.fecha - previa).days
                    cuota.interes = rec.currency_id.round(saldo * ((1 + rec.tea / 100.0) ** (dias / 360.0) - 1))
                saldo -= cuota.capital
                previa = cuota.fecha

    def action_importar(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Cargar cronograma'),
            'res_model': 'promin.obligacion.importar.wizard', 'view_mode': 'form', 'target': 'new',
            'context': {'default_obligacion_id': self.id},
        }

    def action_ver_asientos(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Asientos'), 'res_model': 'account.move',
            'view_mode': 'list,form', 'domain': [('promin_obligacion_id', '=', self.id)],
        }

    # ---------------------------------------------------------------- contabilidad
    def _diario_asientos(self):
        self.ensure_one()
        diario = self.company_id.promin_obl_diario_id or self.env['account.journal'].search([
            ('type', '=', 'general'), ('company_id', '=', self.company_id.id)], limit=1)
        if not diario:
            raise UserError(_('Defina el diario de asientos de obligaciones en la compañía.'))
        return diario

    def _validar_contabilidad(self):
        self.ensure_one()
        if not self.diario_banco_id or not self.diario_banco_id.default_account_id:
            raise UserError(_('Indique el diario del banco (con su cuenta) en la obligación %s.') % self.name)
        if not self.cuenta_pasivo_id:
            raise UserError(_('Indique la cuenta del pasivo en la obligación %s.') % self.name)

    def _crear_asiento(self, fecha, items, ref, cuota=None):
        """items: lista de (cuenta, importe en moneda de la obligación, glosa, partner).
        Importe positivo = debe, negativo = haber. La última línea ajusta el redondeo."""
        self.ensure_one()
        company = self.company_id
        cur = self.currency_id
        ccur = company.currency_id
        items = [it for it in items if it[1]]
        tasa = 1.0
        if cur != ccur:
            tasa = self.env['res.currency']._get_conversion_rate(cur, ccur, company, fecha)
        comandos = []
        acumulado = 0.0
        for idx, (cuenta, importe, glosa, partner) in enumerate(items):
            if idx == len(items) - 1:
                balance = -acumulado
            else:
                balance = ccur.round(importe * tasa)
            acumulado += balance
            vals = {'account_id': cuenta.id, 'name': glosa, 'balance': balance,
                    'partner_id': partner.id if partner else False}
            if cur != ccur:
                vals.update(currency_id=cur.id, amount_currency=importe)
            comandos.append((0, 0, vals))
        move = self.env['account.move'].create({
            'move_type': 'entry', 'date': fecha, 'ref': ref, 'company_id': company.id,
            'journal_id': self._diario_asientos().id,
            'promin_obligacion_id': self.id, 'promin_cuota_id': cuota.id if cuota else False,
            'line_ids': comandos,
        })
        move.action_post()
        return move

    def _saldo_a_fecha(self, fecha):
        """Saldo de capital (moneda de la obligación) a una fecha: 0 si aún no se desembolsa."""
        self.ensure_one()
        if self.state not in ('vigente', 'cancelado') or self.fecha_desembolso > fecha:
            return 0.0
        pagado = sum(self.cuota_ids.filtered(
            lambda c: c.estado == 'pagada' and c.fecha_pago and c.fecha_pago <= fecha).mapped('capital_pagado'))
        return max(self.monto - pagado, 0.0)

    # ------------------------------------------------------------------- alertas
    @api.model
    def _cron_alertas_vencimiento(self):
        hoy = fields.Date.context_today(self)
        for company in self.env['res.company'].search([]):
            dias = company.promin_obl_dias_alerta or 7
            limite = hoy + timedelta(days=dias)
            cuotas = self.env['promin.obligacion.cuota'].sudo().search([
                ('company_id', '=', company.id), ('estado', '=', 'pendiente'),
                ('obligacion_state', '=', 'vigente'), ('alerta_enviada', '=', False),
                ('fecha', '<=', limite)])
            for cuota in cuotas:
                obl = cuota.obligacion_id
                usuario = obl.responsable_id or self.env.ref('base.user_admin', raise_if_not_found=False)
                if not usuario:
                    continue
                obl.activity_schedule(
                    'mail.mail_activity_data_todo', date_deadline=cuota.fecha,
                    summary=_('Vence cuota %(n)s de %(op)s', n=cuota.numero, op=obl.nro_operacion),
                    note=_('%(banco)s - cuota %(n)s por %(monto).2f %(mon)s vence el %(fecha)s.',
                           banco=obl.banco_id.display_name, n=cuota.numero, monto=cuota.total,
                           mon=obl.currency_id.name, fecha=cuota.fecha),
                    user_id=usuario.id)
                cuota.alerta_enviada = True
        return True
