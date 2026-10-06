# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class WizardAsignarCuentas(models.TransientModel):
	_name = 'solse.payroll.asignar.cuentas.wizard'
	_description = 'Asignar cuentas contables a reglas de nómina por prefijo PCGE'

	company_id = fields.Many2one(
		comodel_name='res.company',
		string='Compañía',
		required=True,
		default=lambda self: self.env.company,
	)
	resultado = fields.Text(string='Resultado', readonly=True)
	estado = fields.Selection(
		selection=[('pendiente', 'Pendiente'), ('hecho', 'Ejecutado')],
		default='pendiente',
	)

	def action_asignar(self):
		self.ensure_one()
		mapeo_ids = self.env['solse.payroll.mapeo.contable'].search([])
		if not mapeo_ids:
			self.resultado = _(
				'No hay mapeos contables cargados. Los mapeos por regla se '
				'instalan junto con las reglas salariales (Fase 2) o pueden '
				'crearse manualmente en Nómina PE / Configuración / Mapeo contable.')
			self.estado = 'hecho'
			return self._reabrir()

		aplicados, sin_match = mapeo_ids.aplicar_a_compania(self.company_id)
		lineas = [_('Cuentas asignadas: %s') % aplicados]
		if sin_match:
			lineas.append(_('Prefijos sin cuenta en el plan de "%s":') % self.company_id.name)
			for codigo, campo, prefijo in sin_match:
				sentido = _('débito') if campo == 'account_debit' else _('crédito')
				lineas.append('  - %s (%s): %s' % (codigo, sentido, prefijo))
			lineas.append(_(
				'Cree las cuentas faltantes en el plan contable (o ajuste el '
				'prefijo del mapeo) y vuelva a ejecutar este asistente.'))
		else:
			lineas.append(_('Todos los prefijos resolvieron contra el plan contable.'))
		self.resultado = '\n'.join(lineas)
		self.estado = 'hecho'
		return self._reabrir()

	def _reabrir(self):
		return {
			'type': 'ir.actions.act_window',
			'res_model': self._name,
			'res_id': self.id,
			'view_mode': 'form',
			'target': 'new',
			'name': _('Asignar cuentas contables'),
		}
