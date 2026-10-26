# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SireCrearFacturaWizard(models.TransientModel):
	"""Pide los 4 datos que el usuario siempre completa a mano antes de que
	se genere el borrador de factura de proveedor desde la Propuesta SUNAT."""
	_name = "solse.pe.sire.crear.factura.wizard"
	_description = "Crear factura desde propuesta SUNAT (SIRE)"

	compra_id = fields.Many2one(
		"solse.pe.compras.recibidas", string="Comprobante SIRE",
		required=True, ondelete="cascade", readonly=True,
	)
	company_id = fields.Many2one(
		"res.company", string="Compañía", compute="_compute_company_id",
	)
	etiqueta = fields.Char("Etiqueta", required=True)
	account_id = fields.Many2one(
		"account.account", string="Cuenta", required=True,
		domain="[('company_ids', 'parent_of', company_id),"
		       " ('account_type', 'not in', ('asset_receivable', 'liability_payable', 'off_balance'))]",
	)
	analytic_distribution = fields.Json("Distribución analítica")
	analytic_precision = fields.Integer(
		store=False,
		default=lambda self: self.env["decimal.precision"].precision_get("Percentage Analytic"),
	)
	journal_id = fields.Many2one(
		"account.journal", string="Diario", required=True,
		domain="[('type', '=', 'purchase'), ('company_id', '=', company_id)]",
	)

	@api.depends("compra_id.periodo_id.company_id")
	def _compute_company_id(self):
		for rec in self:
			rec.company_id = rec.compra_id.periodo_id.company_id

	@api.model
	def default_get(self, fields_list):
		res = super().default_get(fields_list)
		compra = self.env["solse.pe.compras.recibidas"].browse(
			res.get("compra_id") or self.env.context.get("default_compra_id")
		)
		if compra:
			res["compra_id"] = compra.id
			company = compra.periodo_id.company_id
			if "journal_id" in fields_list and not res.get("journal_id"):
				journal = self.env["account.journal"].search(
					[("type", "=", "purchase"), ("company_id", "=", company.id)], limit=1
				)
				res["journal_id"] = journal.id
			if "etiqueta" in fields_list and not res.get("etiqueta"):
				lineas = compra.obtener_lineas_a_facturar()
				if lineas:
					res["etiqueta"] = lineas[0][2].get("name")
		return res

	def action_crear_factura(self):
		self.ensure_one()
		if self.compra_id.factura_enlazada:
			raise UserError(_("Este comprobante ya tiene una factura enlazada."))
		self.compra_id.crear_factura(
			etiqueta=self.etiqueta,
			account_id=self.account_id.id,
			analytic_distribution=self.analytic_distribution or False,
			journal_id=self.journal_id.id,
		)
		return {"type": "ir.actions.act_window_close"}
