# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class SolseMigracionNumeroCompra(models.TransientModel):
	"""Diagnostico y migracion del numero de comprobante en compras.

	Contexto
	--------
	Hasta la version 19.0.1.0 de este modulo, el numero del comprobante del
	proveedor se guardaba en `ref` porque `_is_manual_document_number`
	devolvia False tambien en compras y `l10n_latam_document_number` quedaba
	ocupado por el correlativo interno del diario.

	Desde 19.0.1.0 el numero se captura en su campo. Los libros leen primero
	`l10n_latam_document_number` y solo caen en `ref` como respaldo, asi que
	**una base sin migrar sigue emitiendo con normalidad**: migrar es
	opcional y se puede hacer cuando convenga.

	Lo que si conviene hacer siempre es el **diagnostico**: `ref` es texto
	libre y `sire_compra` exigia el formato exacto SERIE-NUMERO. Cualquier
	comprobante con otro formato lleva años saliendo al SIRE con la serie en
	blanco, sin que nada lo avisara. Este asistente los lista.
	"""

	_name = 'solse.migracion.numero.compra'
	_description = 'SOLSE — Número de comprobante en compras'

	company_ids = fields.Many2many(
		comodel_name='res.company',
		string='Compañías',
		default=lambda self: self.env.companies,
		required=True,
	)
	fecha_desde = fields.Date(
		string='Desde',
		help='Deja vacío para revisar todo el histórico.',
	)
	total_compras = fields.Integer(string='Compras revisadas', readonly=True)
	ya_migradas = fields.Integer(
		string='Con número en su campo', readonly=True,
		help='Ya tienen l10n_latam_document_number: no hay nada que hacer.')
	migrables = fields.Integer(
		string='Migrables desde «ref»', readonly=True,
		help='El texto de «ref» tiene formato SERIE-NÚMERO y se puede pasar '
			 'al campo correcto sin intervención.')
	con_formato_invalido = fields.Integer(
		string='Con formato inválido', readonly=True,
		help='Ni el campo ni «ref» permiten separar serie y correlativo. '
			 'Estos comprobantes salen al SIRE con la serie en blanco y hay '
			 'que corregirlos a mano.')
	informe = fields.Text(string='Detalle', readonly=True)
	move_invalidos_ids = fields.Many2many(
		comodel_name='account.move',
		string='Comprobantes a corregir',
		readonly=True,
	)

	# ------------------------------------------------------------ analisis

	def _compras(self):
		self.ensure_one()
		dominio = [
			('move_type', 'in', ('in_invoice', 'in_refund')),
			('company_id', 'in', self.company_ids.ids),
			('state', '!=', 'cancel'),
		]
		if self.fecha_desde:
			dominio.append(('date', '>=', self.fecha_desde))
		return self.env['account.move'].search(dominio, order='date, id')

	@staticmethod
	def _separable(texto):
		"""El texto permite deducir serie y correlativo."""
		texto = (texto or '').strip()
		if '-' not in texto:
			return False
		serie, numero = texto.split('-', 1)
		return bool(serie.strip() and numero.strip())

	def accion_analizar(self):
		self.ensure_one()
		compras = self._compras()
		ya, migrables, invalidos = 0, 0, self.env['account.move']
		lineas = []

		for move in compras:
			propio = (move.l10n_latam_document_number or '').strip()
			if self._separable(propio):
				ya += 1
				continue
			if self._separable(move.ref):
				migrables += 1
				continue
			invalidos |= move
			if len(lineas) < 40:
				lineas.append('· %s · %s · %s · ref=«%s»' % (
					move.date, move.partner_id.display_name[:28],
					move.name or '/', (move.ref or '')[:30]))

		texto = []
		texto.append(_('Compras revisadas: %s', len(compras)))
		texto.append(_('Con el número en su campo: %s', ya))
		texto.append(_('Migrables desde «ref»: %s', migrables))
		texto.append(_('Con formato inválido: %s', len(invalidos)))
		if invalidos:
			texto.append('')
			texto.append(_(
				'Estos comprobantes no permiten deducir serie y correlativo, '
				'así que hoy salen al SIRE con la serie en blanco. Hay que '
				'corregirlos a mano:'))
			texto.append('')
			texto.extend(lineas)
			if len(invalidos) > 40:
				texto.append(_('… y %s más.', len(invalidos) - 40))

		self.write({
			'total_compras': len(compras),
			'ya_migradas': ya,
			'migrables': migrables,
			'con_formato_invalido': len(invalidos),
			'move_invalidos_ids': [(6, 0, invalidos.ids)],
			'informe': '\n'.join(texto),
		})
		return self._recargar()

	# ----------------------------------------------------------- migracion

	def accion_migrar(self):
		"""Pasa el número de «ref» al campo de la localización.

		Se hace uno por uno y capturando el error: escribir el número cambia
		el `name` del asiento, y un asiento ya contabilizado puede tener
		restricciones de secuencia que lo impidan. Los que no se puedan
		migrar se listan y siguen funcionando por el respaldo de «ref».
		"""
		self.ensure_one()
		migrados, fallidos = 0, []

		for move in self._compras():
			if self._separable(move.l10n_latam_document_number):
				continue
			if not self._separable(move.ref):
				continue
			try:
				move.sudo().l10n_latam_document_number = move.ref.strip()
				migrados += 1
			except Exception as error:				# noqa: BLE001
				fallidos.append('· %s · %s: %s' % (
					move.date, move.name or '/', str(error)[:90]))
				_logger.warning('SOLSE · no se pudo migrar el número de %s: %s',
								move.display_name, error)

		texto = [_('Comprobantes migrados: %s', migrados)]
		if fallidos:
			texto.append('')
			texto.append(_(
				'No se pudieron migrar %s. Siguen funcionando con «ref» como '
				'respaldo, así que los libros no se ven afectados:',
				len(fallidos)))
			texto.append('')
			texto.extend(fallidos[:30])
		self.informe = '\n'.join(texto)
		return self._recargar()

	def accion_ver_invalidos(self):
		self.ensure_one()
		return {
			'type': 'ir.actions.act_window',
			'name': _('Comprobantes a corregir'),
			'res_model': 'account.move',
			'view_mode': 'list,form',
			'domain': [('id', 'in', self.move_invalidos_ids.ids)],
		}

	def _recargar(self):
		return {
			'type': 'ir.actions.act_window',
			'res_model': self._name,
			'res_id': self.id,
			'view_mode': 'form',
			'target': 'new',
		}
