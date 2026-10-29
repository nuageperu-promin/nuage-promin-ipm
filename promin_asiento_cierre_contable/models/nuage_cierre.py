from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from . import calculo


class NuageCierre(models.Model):
    _name = 'nuage.cierre'
    _description = 'Cierre y apertura del ejercicio'
    _order = 'anio desc, id desc'
    _sql_constraints = [
        ('anio_company_uniq', 'unique(company_id, anio)',
         'Ya existe un cierre para esa compañía y ese año.'),
    ]

    name = fields.Char(compute='_compute_name', store=True)
    company_id = fields.Many2one('res.company', 'Compañía', required=True, default=lambda s: s.env.company)
    anio = fields.Integer('Año a cerrar', required=True, default=lambda s: date.today().year)
    fecha_cierre = fields.Date(compute='_compute_fechas', store=True)
    fecha_apertura = fields.Date(compute='_compute_fechas', store=True)
    journal_id = fields.Many2one(
        'account.journal', 'Diario', required=True,
        domain="[('company_id', '=', company_id), ('type', '=', 'general')]")
    cuenta_utilidad_id = fields.Many2one(
        'account.account', 'Cuenta resultado - utilidad', required=True,
        domain="[('company_ids', 'in', company_id)]")
    cuenta_perdida_id = fields.Many2one(
        'account.account', 'Cuenta resultado - pérdida', required=True,
        domain="[('company_ids', 'in', company_id)]")
    prefijos_gestion = fields.Char('Clases de gestión (prefijos)', default='6,7', required=True,
                                   help='Cuentas que se cierran contra el resultado, separadas por coma.')
    state = fields.Selection([('draft', 'Borrador'), ('done', 'Generado')], default='draft')
    move_resultados_id = fields.Many2one('account.move', 'Cierre de resultados', readonly=True)
    move_cierre_id = fields.Many2one('account.move', 'Cierre de balance', readonly=True)
    move_apertura_id = fields.Many2one('account.move', 'Apertura', readonly=True)

    @api.depends('company_id', 'anio')
    def _compute_name(self):
        for r in self:
            r.name = _('Cierre %s - %s') % (r.anio, r.company_id.name or '')

    @api.depends('anio')
    def _compute_fechas(self):
        for r in self:
            a = r.anio or date.today().year
            r.fecha_cierre = date(a, 12, 31)
            r.fecha_apertura = date(a + 1, 1, 1)

    # ------------------------------------------------------------------
    def _prefijos(self):
        return tuple(p.strip() for p in (self.prefijos_gestion or '').split(',') if p.strip())

    def _saldos(self, es_gestion):
        """Saldos del ejercicio (posteados) por cuenta, tercero y moneda."""
        self.ensure_one()
        comp = self.company_id
        cuentas = self.env['account.account'].with_company(comp).search(
            [('company_ids', 'in', comp.id)])
        pref = self._prefijos()
        ids = cuentas.filtered(
            lambda a: bool(a.code) and (a.code.startswith(pref) == es_gestion)).ids
        if not ids:
            return []
        dominio = [
            ('company_id', '=', comp.id), ('parent_state', '=', 'posted'),
            ('date', '>=', date(self.anio, 1, 1)), ('date', '<=', self.fecha_cierre),
            ('account_id', 'in', ids),
        ]
        grupos = self.env['account.move.line']._read_group(
            dominio, ['account_id', 'partner_id', 'currency_id'],
            ['balance:sum', 'amount_currency:sum'])
        res = []
        for cuenta, partner, moneda, bal, imp in grupos:
            if comp.currency_id.is_zero(bal) and moneda.is_zero(imp):
                continue
            usa_moneda = moneda and moneda != comp.currency_id
            res.append({
                'account_id': cuenta.id,
                # tercero solo en cuentas conciliables (por cobrar / por pagar)
                'partner_id': partner.id if (partner and cuenta.reconcile) else False,
                'currency_id': moneda.id if usa_moneda else comp.currency_id.id,
                'balance': bal,
                'amount_currency': imp if usa_moneda else bal,
            })
        return self._agrupar(res)

    @staticmethod
    def _agrupar(lineas):
        """Une lineas que quedaron con la misma cuenta/tercero/moneda."""
        acc = {}
        for l in lineas:
            k = (l['account_id'], l['partner_id'], l['currency_id'])
            if k in acc:
                acc[k]['balance'] += l['balance']
                acc[k]['amount_currency'] += l['amount_currency']
            else:
                acc[k] = dict(l)
        return list(acc.values())

    def _crear_asiento(self, fecha, ref, lineas, **extra):
        vals = {
            'move_type': 'entry', 'journal_id': self.journal_id.id, 'date': fecha,
            'ref': ref, 'company_id': self.company_id.id,
            'line_ids': [(0, 0, dict(l, name=ref)) for l in lineas],
        }
        vals.update(extra)
        vals['nuage_cierre_id'] = self.id
        move = self.env['account.move'].with_company(self.company_id).create(vals)
        move.action_post()
        return move

    def action_generar(self):
        self.ensure_one()
        if self.state == 'done':
            raise UserError(_('El cierre ya fue generado. Revíertalo antes de generarlo otra vez.'))
        # 1) Cierre de resultados
        gestion = self._saldos(True)
        total = sum(l['balance'] for l in gestion)
        destino = calculo.destino_resultado(total)
        lineas1 = calculo.invertir(gestion)
        if destino:
            cuenta = self.cuenta_utilidad_id if destino == 'utilidad' else self.cuenta_perdida_id
            lineas1.append({
                'account_id': cuenta.id, 'partner_id': False,
                'currency_id': self.company_id.currency_id.id,
                'balance': total, 'amount_currency': total,
            })
        if lineas1:
            self.move_resultados_id = self._crear_asiento(
                self.fecha_cierre, _('Cierre de resultados %s') % self.anio, lineas1,
                es_x_cierre=True)
        # 2) Cierre de balance (incluye la cuenta de resultado ya cargada)
        balance = self._saldos(False)
        if not balance:
            raise UserError(_('No hay saldos de balance para cerrar en %s.') % self.anio)
        self.move_cierre_id = self._crear_asiento(
            self.fecha_cierre, _('Cierre de balance %s') % self.anio,
            calculo.invertir(balance), es_x_cierre=True)
        # 3) Apertura del siguiente ejercicio
        self.move_apertura_id = self._crear_asiento(
            self.fecha_apertura, _('Apertura %s') % (self.anio + 1), balance,
            es_x_apertura=True, fecha_apertura=self.fecha_apertura)
        self.state = 'done'

    def action_revertir(self):
        for r in self:
            for m in (r.move_apertura_id | r.move_cierre_id | r.move_resultados_id):
                if m.state == 'posted':
                    m.button_draft()
                m.unlink()
            r.state = 'draft'


class AccountMove(models.Model):
    _inherit = 'account.move'

    nuage_cierre_id = fields.Many2one(
        'nuage.cierre', string='Cierre contable', copy=False, index='btree_not_null', ondelete='set null',
        help='Cierre y apertura que generó este asiento. Los estados financieros '
             'que lo requieren (p. ej. cambios en el patrimonio) lo excluyen.')
