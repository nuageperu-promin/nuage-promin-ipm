# -*- coding: utf-8 -*-

from datetime import date, timedelta

from odoo.tests.common import TransactionCase


class TestGuiaCommon(TransactionCase):
	"""Setup compartido para tests del módulo solse_pe_cpe_guias.

	Crea datos mínimos para poder instanciar pickings con los campos pe_*
	necesarios para invocar las validaciones cliente-side. NO crea datos
	completos para envío real a SUNAT (firma, certificados, etc.).
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.PartnerObj = cls.env['res.partner'].sudo()
		cls.PickingObj = cls.env['stock.picking'].sudo()
		cls.ProductObj = cls.env['product.product'].sudo()
		cls.DocRelObj = cls.env['pe.stock.documento.relacionado'].sudo()
		cls.ContObj = cls.env['pe.stock.contenedor'].sudo()
		cls.PeDatas = cls.env['pe.datas'].sudo()

		# Tipo de identificación RUC (catálogo 06 SUNAT código 6)
		cls.tipo_ruc = cls.env['l10n_latam.identification.type'].sudo().search(
			[('l10n_pe_vat_code', '=', '6')], limit=1
		)
		cls.tipo_dni = cls.env['l10n_latam.identification.type'].sudo().search(
			[('l10n_pe_vat_code', '=', '1')], limit=1
		)

		# Partners de prueba
		cls.partner_remitente = cls._crear_partner_ruc(
			'Empresa Remitente SAC', '20100000001'
		)
		cls.partner_cliente = cls._crear_partner_ruc(
			'Empresa Cliente SAC', '20200000002'
		)
		cls.partner_emisor_doc = cls._crear_partner_ruc(
			'Emisor Documento SAC', '20300000003'
		)
		cls.partner_terminal_portuario = cls._crear_partner_ruc(
			'Terminal Portuario SAC', '20400000004'
		)

		# Almacén / tipo de picking de salida (out)
		cls.warehouse = cls.env['stock.warehouse'].sudo().search(
			[('company_id', '=', cls.env.company.id)], limit=1
		)
		cls.picking_type_out = cls.warehouse.out_type_id

		# Producto
		cls.producto = cls.ProductObj.create({
			'name': 'Producto Test SUNAT',
			'type': 'consu',
			'default_code': 'TEST-001',
		})

	@classmethod
	def _crear_partner_ruc(cls, nombre, ruc):
		"""Crea un partner con RUC válido formato peruano (11 dígitos)."""
		vals = {
			'name': nombre,
			'company_type': 'company',
			'vat': ruc,
			'commercial_name': nombre,
		}
		if cls.tipo_ruc:
			vals['l10n_latam_identification_type_id'] = cls.tipo_ruc.id
		return cls.PartnerObj.create(vals)

	def _crear_picking(self, **overrides):
		"""Crea un picking con valores por defecto sensatos.
		Acepta overrides para sobrescribir campos puntuales.
		"""
		vals = {
			'partner_id': self.partner_cliente.id,
			'picking_type_id': self.picking_type_out.id,
			'location_id': self.picking_type_out.default_location_src_id.id,
			'location_dest_id': self.partner_cliente.property_stock_customer.id,
			'pe_is_eguide': True,
			'pe_transfer_code': '01',
			'pe_gross_weight': 100.0,
			'pe_unit_quantity': 1,
			'pe_transport_mode': '02',
			'pe_date_issue': date.today(),
		}
		vals.update(overrides)
		return self.PickingObj.create(vals)
