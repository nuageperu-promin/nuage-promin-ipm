# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command
import logging

_logger = logging.getLogger(__name__)


class LineaAfectacionCompra(models.Model):
	_name = "solse.pe.afectacion.compra"
	_description = "Linea Afectación Compra"
	_order = "sequence, name"

	name = fields.Char("Nombre", required=True, translate=True)
	codigo = fields.Char(
		"Código",
		help="Código informativo de referencia (ej: '10' para Gravada, '20' para Exonerada).",
	)
	categoria = fields.Selection(
		[
			('gravada_dg',     'Gravada destinada a op. gravadas'),
			('gravada_dgng',   'Gravada destinada a op. gravadas y no gravadas (mixta)'),
			('gravada_dng',    'Gravada destinada a op. no gravadas (sin crédito fiscal)'),
			('exonerada',      'Exonerada'),
			('inafecta',       'Inafecta'),
			('importacion',    'Importación de bienes (DAM/DSI)'),
			('no_domiciliado', 'Operación con sujeto no domiciliado'),
			('excluir',        'No considerar en libros (uso interno)'),
		],
		string="Categoría",
		help="Clasificación funcional usada por los libros SIRE para distribuir "
			 "los montos en sus columnas correspondientes.",
	)
	active = fields.Boolean(default=True)
	sequence = fields.Integer(default=10)

	aplica_rce = fields.Boolean(
		string="Aplica al RCE 8.4 (compras nacionales)",
		default=True,
		help="Si está activo, las líneas con esta afectación se incluyen en "
			 "el SIRE Registro de Compras 8.4. Desactivar para líneas "
			 "internas que no deben aparecer en el libro.",
	)
	aplica_rce_no_dom = fields.Boolean(
		string="Aplica al RCE 8.5 (no domiciliados)",
		default=False,
		help="Si está activo, las líneas con esta afectación se incluyen en "
			 "el SIRE Registro de Compras de operaciones con no domiciliados 8.5.",
	)

	impuesto_afect_ids = fields.One2many(
		comodel_name="solse.pe.impuesto.afectacion.compra",
		inverse_name="linea_afectacion_id",
		string="Impuestos permitidos",
	)
	impuesto_defecto_ids = fields.Many2many(
		comodel_name="solse.pe.impuesto.afectacion.compra",
		relation="solse_pe_afect_compra_imp_def_rel",
		column1="afectacion_id",
		column2="impuesto_afect_id",
		domain="[('id', 'in', impuesto_afect_ids)]",
		string="Impuestos por defecto",
		help="Impuestos que se asignan automáticamente a la línea de factura "
			 "al seleccionar este tipo de afectación. Soporta múltiples "
			 "impuestos para casos como retenciones (IGV + retención).",
	)
	nro_col_importe_afectacion = fields.Integer(
		"Columna SIRE (sin impuesto)",
		help="Columna del libro SIRE donde va el monto cuando la línea NO tiene "
			 "impuestos vinculados (caso típico: exoneradas/inafectas → col 21).",
	)
	toma_para_calculo = fields.Selection(
		[('total', 'Total'), ('impuesto', 'Impuesto'), ('base', 'Base')],
		default="base",
		string="Valor para Cálculo (sin impuesto)",
		help="Indica qué valor de la línea se suma a la columna SIRE cuando "
			 "no hay impuestos: total (price_total), impuesto (diferencia) o base (price_subtotal).",
	)


class ImpuestoAfectacionCompra(models.Model):
	_name = "solse.pe.impuesto.afectacion.compra"
	_description = "Impuesto Afectación Compra"

	active = fields.Boolean(default=True)
	linea_afectacion_id = fields.Many2one("solse.pe.afectacion.compra", string="Afectación compra")
	impuesto_id = fields.Many2one("account.tax", string="Impuesto")
	name = fields.Char("Nombre", related="impuesto_id.name")
	nro_col_importe_impuesto = fields.Integer(
		"Columna Importe Impuesto",
		help="Columna del libro SIRE donde se sumará el valor calculado.",
	)
	toma_para_calculo = fields.Selection(
		[('total', 'Total'), ('impuesto', 'Impuesto'), ('base', 'Base')],
		default="base",
		string="Valor para Cálculo",
		help="Qué parte de la línea sumar a la columna: "
			 "base (price_subtotal), impuesto (price_total - price_subtotal) o total (price_total).",
	)


class AccountMove(models.Model):
	_inherit = 'account.move'

	def _get_view(self, view_id=None, view_type='form', **options):
		arch, view = super()._get_view(view_id, view_type, **options)
		if view_type != 'form':
			return arch, view

		paso_validacion = False
		ctx = self.env.context

		if ctx.get('params') and 'action' in ctx['params']:
			accion = self.env['ir.actions.act_window'].sudo().search(
				[('id', '=', ctx['params']['action'])], limit=1
			)
			if accion and accion.domain and (
				'in_invoice' in accion.domain or 'in_refund' in accion.domain
			):
				paso_validacion = True
		elif options and 'action_id' in options:
			accion = self.env['ir.actions.act_window'].sudo().search(
				[('id', '=', options['action_id'])], limit=1
			)
			if accion and accion.domain and (
				'in_invoice' in accion.domain or 'in_refund' in accion.domain
			):
				paso_validacion = True
		elif ctx.get('default_move_type') in ['in_invoice', 'in_refund']:
			paso_validacion = True

		if paso_validacion:
			for nodo in arch.xpath("//field[@name='tipo_afectacion_compra']"):
				nodo.set('invisible', '0')
				nodo.set('column_invisible', '0')

		return arch, view


class AccountMoveLine(models.Model):
	_inherit = 'account.move.line'

	tipo_afectacion_compra = fields.Many2one(
		"solse.pe.afectacion.compra",
		string='Tipo de afectación',
		help='Tipo de afectación Compra',
		store=True,
	)

	@api.onchange('tipo_afectacion_compra')
	def onchange_tipo_afectacion_compra(self):
		if self.move_id.move_type not in ['in_invoice', 'in_refund']:
			return
		if not self.tipo_afectacion_compra:
			return

		# AFE-01 (L4b.4): RESPETAR LA LÍNEA va PRIMERO. Si el impuesto
		# actual ya está entre los permitidos de la afectación, no se
		# reemplaza nada: una línea con el IGV 10,5 % (Ley 31556) mapeado
		# en la afectación gravada era pisada por el IGV 18 por defecto
		# en cuanto se tocaba la afectación — exactamente el síntoma que
		# reportó el cliente. El reemplazo por defecto (multi-impuesto,
		# retenciones) queda para las líneas cuyo impuesto NO pertenece
		# a la afectación elegida.
		impuestos_validos_ids = self.tipo_afectacion_compra.impuesto_afect_ids.mapped('impuesto_id').ids
		if self.tax_ids and self.tax_ids[0]._origin.id in impuestos_validos_ids:
			return

		# Caso 1: la afectación tiene impuestos por defecto configurados.
		# Se reemplazan los impuestos de la línea con el conjunto configurado
		# (cubre casos multi-impuesto como retenciones: IGV + retención IGV).
		# A-12 (L3): la afectación es global y sus líneas mezclan impuestos
		# de TODAS las compañías — todo consumo filtra por la compañía de la
		# línea, o un Command.set colocaría impuestos ajenos en la factura.
		compania = self.company_id or self.move_id.company_id
		impuestos_defecto = self.tipo_afectacion_compra.impuesto_defecto_ids.mapped(
			'impuesto_id').filtered(lambda t: t.company_id == compania)
		if impuestos_defecto:
			self.tax_ids = [Command.set(impuestos_defecto.ids)]
			return

		# Caso fallback: primer impuesto permitido DE ESTA COMPAÑÍA (si existe).
		primer_impuesto = self.tipo_afectacion_compra.impuesto_afect_ids.mapped(
			'impuesto_id').filtered(lambda t: t.company_id == compania)[:1]
		if primer_impuesto:
			self.tax_ids = [Command.set([primer_impuesto.id])]

	def _asignar_afectacion_por_impuesto(self):
		"""Asigna tipo_afectacion_compra buscando qué afectación contiene
		el impuesto principal (el primero) de la línea."""
		if not self.tax_ids:
			return
		impuesto = self.tax_ids[0]
		afectaciones = self.env['solse.pe.afectacion.compra'].search([
			('aplica_rce', '=', True),  # priorizar afectaciones de RCE 8.4
		])
		for afectacion in afectaciones:
			if impuesto._origin.id in afectacion.impuesto_afect_ids.mapped('impuesto_id').ids:
				self.tipo_afectacion_compra = afectacion
				return

	@api.onchange('tax_ids')
	def _onchange_impuesto_compra(self):
		if self.move_id.move_type in ['in_invoice', 'in_refund']:
			self._asignar_afectacion_por_impuesto()

	@api.onchange('product_id')
	def _onchange_purchase_product_id(self):
		for rec in self.filtered(lambda x: x.product_id and x.move_id.move_type in ['in_invoice', 'in_refund']):
			rec._asignar_afectacion_por_impuesto()
