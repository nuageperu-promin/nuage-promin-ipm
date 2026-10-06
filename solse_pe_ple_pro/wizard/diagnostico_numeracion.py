# -*- coding: utf-8 -*-

import logging
import re

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)

# Serie de cuatro caracteres, guion y correlativo. Es el formato que exigen
# el registro de compras, el SIRE y el PLE.
FORMATO_COMPROBANTE = re.compile(r'^[A-Z0-9]{1,4}\-\d{1,20}$')


class SolseDiagnosticoNumeracion(models.TransientModel):
	"""Revisa que cada compra tenga un número de comprobante utilizable.

	Por qué hace falta
	------------------
	Hasta la versión 19.0.1.0, el número del comprobante del proveedor se
	guardaba en `ref`, un campo de texto libre. Los libros lo parteaban con
	`ref.split("-")` esperando exactamente dos partes, y cuando el texto no
	tenía ese formato —«F001-123 (rectificada)», «FACT 001-123», o
	simplemente vacío— la serie y el correlativo salían **vacíos sin avisar**
	y el SIRE se enviaba incompleto.

	Desde esta versión el número se captura en `l10n_latam_document_number`,
	que sí tiene formato garantizado y unicidad por proveedor. Las bases
	anteriores siguen funcionando porque el helper mantiene `ref` como
	respaldo, pero conviene saber cuántos comprobantes quedaron con un número
	que ningún libro va a poder leer.

	Este asistente no modifica nada: solo señala qué hay que corregir.
	"""

	_name = 'solse.diagnostico.numeracion'
	_description = 'SOLSE — Diagnóstico de numeración de compras'

	fecha_desde = fields.Date(
		string='Desde',
		required=True,
		default=lambda self: fields.Date.context_today(self).replace(
			month=1, day=1),
	)
	fecha_hasta = fields.Date(
		string='Hasta',
		required=True,
		default=fields.Date.context_today,
	)
	company_id = fields.Many2one(
		comodel_name='res.company',
		string='Compañía',
		required=True,
		default=lambda self: self.env.company,
	)
	resultado = fields.Text(string='Resultado', readonly=True)
	total_revisadas = fields.Integer(string='Compras revisadas', readonly=True)
	total_correctas = fields.Integer(string='Con número válido', readonly=True)
	total_observadas = fields.Integer(string='Observadas', readonly=True)
	move_observado_ids = fields.Many2many(
		comodel_name='account.move',
		string='Comprobantes observados',
		readonly=True,
	)

	def accion_diagnosticar(self):
		self.ensure_one()
		compras = self.env['account.move'].search([
			('company_id', '=', self.company_id.id),
			('move_type', 'in', ('in_invoice', 'in_refund')),
			('state', '=', 'posted'),
			('date', '>=', self.fecha_desde),
			('date', '<=', self.fecha_hasta),
		], order='date, id')

		observadas = self.env['account.move']
		motivos = []
		vistos = {}
		duplicadas = []

		for compra in compras:
			numero = (compra.get_sunat_number()
					  if hasattr(compra, 'get_sunat_number')
					  else (compra.ref or ''))
			numero = (numero or '').strip().upper()

			if not numero:
				observadas |= compra
				motivos.append((compra, _('sin número de comprobante')))
				continue
			if not FORMATO_COMPROBANTE.match(numero):
				observadas |= compra
				motivos.append((compra, _(
					'formato no válido: «%s» (se espera SERIE-CORRELATIVO)',
					numero)))
				continue

			# Un mismo numero del mismo proveedor dos veces es, casi siempre,
			# la misma factura registrada dos veces.
			clave = (compra.partner_id.id, numero)
			if clave in vistos:
				observadas |= compra
				duplicadas.append((compra, vistos[clave]))
				motivos.append((compra, _(
					'número repetido para el mismo proveedor (ya está en %s)',
					vistos[clave].name)))
				continue
			vistos[clave] = compra

		lineas = [
			_('Compras revisadas: %s', len(compras)),
			_('Con número válido: %s', len(compras) - len(observadas)),
			_('Observadas: %s', len(observadas)),
		]
		if duplicadas:
			lineas.append(_('Posibles duplicados: %s', len(duplicadas)))
		if motivos:
			lineas.append('')
			lineas.append(_('DETALLE'))
			for compra, motivo in motivos[:200]:
				lineas.append('· %s — %s — %s' % (
					fields.Date.to_string(compra.date),
					compra.partner_id.display_name or _('sin proveedor'),
					motivo))
			if len(motivos) > 200:
				lineas.append(_('… y %s más.', len(motivos) - 200))
		else:
			lineas.append('')
			lineas.append(_(
				'Todos los comprobantes de compra tienen serie y correlativo '
				'legibles para el registro de compras, el SIRE y el PLE.'))

		self.write({
			'total_revisadas': len(compras),
			'total_correctas': len(compras) - len(observadas),
			'total_observadas': len(observadas),
			'move_observado_ids': [(6, 0, observadas.ids)],
			'resultado': '\n'.join(lineas),
		})
		return {
			'type': 'ir.actions.act_window',
			'res_model': self._name,
			'res_id': self.id,
			'view_mode': 'form',
			'target': 'new',
		}

	def accion_ver_observados(self):
		self.ensure_one()
		return {
			'type': 'ir.actions.act_window',
			'name': _('Comprobantes de compra observados'),
			'res_model': 'account.move',
			'view_mode': 'list,form',
			'domain': [('id', 'in', self.move_observado_ids.ids)],
		}
