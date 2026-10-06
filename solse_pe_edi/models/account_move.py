# -*- coding: utf-8 -*-

from odoo import api, fields, tools, models, _
from odoo.exceptions import UserError, RedirectWarning
import logging
import re
_logging = logging.getLogger(__name__)

TYPE2JOURNAL = {
	'out_invoice':'sale', 
	'in_invoice':'purchase',  
	'out_refund':'sale', 
	'in_refund':'purchase'
}
 
# A-5 / M-35 · dependencias del cómputo de detracción y retención.
#
# Viven aquí, a nivel de módulo, para que cualquier módulo que redefina
# `_compute_detraccion_retencion` pueda ESCRIBIRLAS POR REFERENCIA:
#
#     from odoo.addons.solse_pe_edi.models.account_move import (
#         DEPENDS_DETRACCION_RETENCION)
#
#     @api.depends(*DEPENDS_DETRACCION_RETENCION, 'aplica_detraccion')
#     def _compute_detraccion_retencion(self): ...
#
# `@api.depends` de un override REEMPLAZA al del padre. Copiarlas a mano es
# lo que hizo que la corrección de A-5 no llegara a ninguna base real.
DEPENDS_DETRACCION_RETENCION = (
	'move_type', 'amount_total', 'amount_total_signed', 'currency_id',
	'invoice_line_ids.product_id.aplica_detraccion',
	'invoice_line_ids.product_id.detraccion_id',
	'invoice_line_ids.product_id.detraccion_id.value',
	'partner_id.doc_type',
	'partner_id.buen_contribuyente',
	'partner_id.es_agente_retencion',
	'company_id.monto_detraccion',
	'company_id.agente_retencion',
	'company_id.currency_id',
	'porc_retencion',
	'retencion_manual',
)


class AccountMove(models.Model):
	_inherit = 'account.move'

	amount_text = fields.Char("Monto en letras", compute="_get_amount_text")
	is_cpe = fields.Boolean('Es CPE', related='l10n_latam_document_type_id.is_cpe', store=True)
	usar_prefijo_personalizado = fields.Boolean('Personalizar prefijo', related='l10n_latam_document_type_id.usar_prefijo_personalizado', store=True)
	usar_prefijo_sin_localizacion = fields.Boolean(
		'Usar prefijo sin localización',
		related='l10n_latam_document_type_id.usar_prefijo_sin_localizacion',
		store=True
	)
	pe_sunat_transaction51 = fields.Selection('_get_pe_sunat_transaction51', string='Tipo de transacción de Sunat', default='0101', readonly=True)

	moneda_base = fields.Many2one('res.currency', string="Moneda base", related="company_id.currency_id", store=True)
	monto_base_detraccion = fields.Float(string='Monto base detracción', related="company_id.monto_detraccion", store=True)
	
	cuenta_detraccion = fields.Many2one('account.journal', related='company_id.cuenta_detraccion')
	nro_cuenta_detraccion = fields.Char('Cuenta de detracción', compute='_compute_cuenta_detraccion')

	tiene_detraccion = fields.Boolean('Tiende detracción', compute="_compute_detraccion_retencion", store=True)
	detraccion_id = fields.Selection("_get_pe_type_detraccion", string="Detracción", compute="_compute_detraccion_retencion", store=True)
	porc_detraccion = fields.Float(string='% Detracción', compute="_compute_detraccion_retencion", store=True)
	monto_detraccion = fields.Monetary('Monto detracción S/', currency_field='moneda_base', compute="_compute_detraccion_retencion", store=True)
	monto_detraccion_base = fields.Monetary('Monto detracción', currency_field='currency_id',compute="_compute_detraccion_retencion", store=True)

	retencion_manual = fields.Boolean(
		string='Forzar retención',
		help='Marcar cuando la operación está sujeta a retención y el '
			 'criterio automático no la detecta. El automático la aplica '
			 'cuando la compañía es agente de retención (compras) o cuando '
			 'el cliente lo es (ventas).')
	tiene_retencion = fields.Boolean(string='Tiene retención', compute="_compute_detraccion_retencion", store=True)
	porc_retencion = fields.Float(string='% Retención', related="company_id.por_retencion", store=True)
	monto_retencion = fields.Monetary(string='Monto retención S/', currency_field='moneda_base', compute="_compute_detraccion_retencion", store=True)
	monto_retencion_base = fields.Monetary(string='Monto retención', currency_field='currency_id', compute="_compute_detraccion_retencion", store=True)

	monto_neto_pagar = fields.Monetary(string="Neto Pagar S/", currency_field='moneda_base', compute="_compute_detraccion_retencion", store=True)
	monto_neto_pagar_base = fields.Monetary(string="Neto Pagar", currency_field='currency_id', compute="_compute_detraccion_retencion", store=True)

	annul = fields.Boolean('Anulado', readonly=True)
	state = fields.Selection(selection_add=[('annul', 'Anulado'), ], ondelete={'annul': 'cascade'})
	status_in_payment = fields.Selection(selection_add=[('annul', 'Anulado'), ], ondelete={'annul': 'cascade'})

	tipo_transaccion = fields.Selection([('contado', 'Contado'), ('credito', 'Credito')], string='Tipo de Transacción', default='contado')
	pe_branch_code = fields.Char("Codigo Sucursal", default="0000")
	sub_type = fields.Selection([('sale', 'Venta'), ('purchase', 'Compras')], compute="_compute_sub_type", store=True)

	def _compute_cuenta_detraccion(self):
		for reg in self:
			if reg.company_id.cuenta_detraccion and reg.company_id.cuenta_detraccion.bank_account_id:
				reg.nro_cuenta_detraccion =  reg.company_id.cuenta_detraccion.name +': '+ reg.company_id.cuenta_detraccion.bank_account_id.acc_number
			else:
				reg.nro_cuenta_detraccion = ''

	# A-5 / M-35. Las dependencias van en una CONSTANTE DE MÓDULO y no
	# escritas a mano en el decorador, porque `@api.depends` de un override
	# REEMPLAZA al del padre, no lo extiende. `solse_pe_accountant` redefine
	# este compute y copió la lista de seis que había aquí: al completarla
	# en L7.2, su copia quedó atrás y la corrección de A-5 no llegaba a
	# ninguna base con la suite contable instalada. Con la constante, el
	# hijo hace `@api.depends(*DEPENDS_DETRACCION_RETENCION, 'lo suyo')` y
	# no hay nada que mantener sincronizado a mano.
	# A-5. Declaraba seis dependencias y el cómputo leía siete campos más de
	# `company_id` y `partner_id`. Consecuencias medidas: cambiar el umbral
	# de detracción de la compañía no recalculaba las facturas, y marcar a
	# un proveedor como buen contribuyente no le quitaba la retención ya
	# calculada. El orden de escritura decidía el resultado, y por eso el
	# sembrado del laboratorio OBLIGA a configurar la compañía antes de
	# crear facturas.
	#
	# `invoice_date_due` e `invoice_payment_term_id` estaban declarados y no
	# se leen: se retiran, solo provocaban recálculos inútiles.
	@api.depends(*DEPENDS_DETRACCION_RETENCION)
	def _compute_detraccion_retencion(self):
		for reg in self:
			#_logging.info('datos de la detraccion')
			#_logging.info(reg.tiene_detraccion)
			datos = reg._validar_detraccion_retencion(reg.retencion_manual)
			reg.tiene_detraccion = datos['tiene_detraccion']
			reg.detraccion_id = datos['detraccion_id']
			reg.porc_detraccion = datos['porc_detraccion']
			monto_detraccion = datos['monto_detraccion']
			monto_detraccion_base = datos['monto_detraccion_base']

			reg.tiene_retencion = datos['tiene_retencion']
			monto_retencion = datos['monto_retencion']
			monto_retencion_base = datos['monto_retencion_base']

			reg.monto_retencion = monto_retencion	
			reg.monto_retencion_base = monto_retencion_base

			if reg.currency_id.id != reg.company_id.currency_id.id:
				monto_neto_pagar = abs(reg.amount_total_signed) - monto_detraccion - monto_retencion
				monto_neto_pagar_base = abs(reg.amount_total) - monto_detraccion_base - monto_retencion_base

				monto_detraccion = self.redondear_decimales(monto_detraccion)
				reg.monto_detraccion = monto_detraccion
				reg.monto_neto_pagar = monto_neto_pagar
				reg.monto_neto_pagar_base = monto_neto_pagar_base

				monto_detraccion_base = self.redondear_decimales_total_base(monto_detraccion_base)
				reg.monto_detraccion_base = monto_detraccion_base
			else:
				monto_detraccion = self.redondear_decimales(monto_detraccion)
				monto_neto_pagar = abs(reg.amount_total_signed) - monto_detraccion - monto_retencion
				monto_neto_pagar_base = abs(reg.amount_total) - monto_detraccion_base - monto_retencion_base

				reg.monto_detraccion = monto_detraccion
				reg.monto_neto_pagar = self.redondear_decimales_total(monto_neto_pagar)
				reg.monto_neto_pagar_base = self.redondear_decimales_total(monto_neto_pagar_base)

				monto_detraccion_base = monto_detraccion_base
				reg.monto_detraccion_base = self.redondear_decimales(monto_detraccion_base)

			if reg.tiene_detraccion:
				reg.pe_sunat_transaction51 = '1001'
			elif reg.pe_sunat_transaction51 == '1001':
				reg.pe_sunat_transaction51 = '0101'

	def redondear_decimales(self, monto):
		return round(monto, 0)

	def redondear_decimales_retencion(self, monto):
		return round(monto, 2)

	def redondear_decimales_total(self, monto):
		return round(monto, 2)

	def redondear_decimales_total_base(self, monto):
		return round(monto, 2)


	@api.depends('amount_total')
	def _get_amount_text(self):
		_logging.info("********************************************")
		for invoice in self:
			if invoice.amount_total<2 and invoice.amount_total>=1:
				currency_name = invoice.currency_id.singular_name or invoice.currency_id.plural_name or invoice.currency_id.name or ""
			else:
				currency_name = invoice.currency_id.plural_name or invoice.currency_id.name or ""

			_logging.info("nombre moneda aaa")
			_logging.info(currency_name)
			fraction_name = invoice.currency_id.fraction_name or ""
			amount_text = invoice.currency_id.amount_to_text(invoice.amount_total)
			_logging.info("retorno del textooooooooooooooooooooooooooo")
			_logging.info(amount_text)
			_logging.info("invoice.currency_id.plural_name")
			_logging.info(invoice.currency_id.plural_name)
			invoice.amount_text= amount_text

	@api.model
	def _get_pe_sunat_transaction51(self):
		return self.env['pe.datas'].get_selection('PE.CPE.CATALOG51')

	# A-5. Aquí vivía un `@api.onchange('tiene_retencion')` que replicaba
	# medio cómputo. Era código muerto: `tiene_retencion` es compute+store
	# sin `readonly=False`, así que el ORM lo hace readonly y el onchange
	# nunca podía dispararse. La marca manual es ahora `retencion_manual`,
	# que es una dependencia declarada del cómputo — no hace falta
	# duplicar nada.

	def _validar_detraccion_retencion(self, forzar_retencion):
		datos_rpt = {
			"tiene_detraccion": False,
			"detraccion_id": False,
			"porc_detraccion": 0.0,
			"monto_detraccion": 0.0,
			"monto_detraccion_base": 0.0,
			"tiene_retencion": False,
			"monto_retencion": 0.0,
			"monto_retencion_base": 0.0,
		}
		if abs(self.amount_total_signed) < self.company_id.monto_detraccion or self.partner_id.doc_type != "6":
			return datos_rpt

		tiene_detraccion = False
		detraccion_id = False

		for linea in self.invoice_line_ids:
			if linea.product_id.aplica_detraccion:
				tiene_detraccion = True
				detraccion_id = linea.product_id.detraccion_id
		
		if tiene_detraccion:
			monto_detraccion = abs(self.amount_total_signed) * (detraccion_id.value / 100.0) if detraccion_id.value > 0 else 0.0
			monto_detraccion_base = abs(self.amount_total) * (detraccion_id.value / 100.0) if detraccion_id.value > 0 else 0.0

			datos_rpt = {
				"tiene_detraccion": True,
				"detraccion_id": detraccion_id.code,
				"porc_detraccion": detraccion_id.value,
				"monto_detraccion": monto_detraccion,
				"monto_detraccion_base": monto_detraccion_base,
				"tiene_retencion": False,
				"monto_retencion": 0.0,
				"monto_retencion_base": 0.0,
			}
			return datos_rpt

		if self.partner_id.buen_contribuyente and self.move_type in ['in_invoice', 'in_refund']:
			return datos_rpt

		
		porc_retencion = self.porc_retencion		
		monto_retencion = abs(self.amount_total_signed) * (porc_retencion / 100.0)
		monto_retencion = self.redondear_decimales_retencion(monto_retencion)
		monto_retencion_base = abs(self.amount_total) * (porc_retencion / 100.0)
		#monto_retencion_base = round(monto_retencion_base)
		if self.currency_id.id == self.company_id.currency_id.id:
			monto_retencion_base = self.redondear_decimales_retencion(monto_retencion_base)
		if self.company_id.agente_retencion and self.move_type in ['in_invoice', 'in_refund']:
			datos_rpt = {
				"tiene_detraccion": False,
				"detraccion_id": False,
				"porc_detraccion": 0.0,
				"monto_detraccion": 0.0,
				"monto_detraccion_base": 0.0,
				"tiene_retencion": True,
				"monto_retencion": monto_retencion,
				"monto_retencion_base": monto_retencion_base,
			}
		# A-5. Aquí estaba `self.tiene_retencion or ...`: el cómputo leía el
		# campo que estaba calculando, o sea su valor ANTERIOR. Una vez True,
		# la retención no se quitaba nunca por mucho que cambiaran los datos.
		# La intención —permitir marcarla a mano— vive ahora en
		# `retencion_manual`, que el cómputo recibe como `forzar_retencion`.
		elif self.move_type in ['out_invoice', 'out_refund'] and (forzar_retencion or self.partner_id.es_agente_retencion):
			datos_rpt = {
				"tiene_detraccion": False,
				"detraccion_id": False,
				"porc_detraccion": 0.0,
				"monto_detraccion": 0.0,
				"monto_detraccion_base": 0.0,
				"tiene_retencion": True,
				"monto_retencion": monto_retencion,
				"monto_retencion_base": monto_retencion_base,
			}
		return datos_rpt


	@api.depends('move_type')
	def _compute_sub_type(self):
		for reg in self:
			if reg.move_type in TYPE2JOURNAL:
				reg.sub_type = TYPE2JOURNAL[reg.move_type]
			else:
				reg.sub_type = False

	@api.model
	def _get_pe_type_detraccion(self):
		return self.env['pe.datas'].get_selection("PE.CPE.CATALOG54")

	def _obtener_serie_correlativo(self):
		number_match = [rn for rn in re.finditer(r'\d+', self.name.replace(' ', ''))]
		serie = self.name[:number_match[-1].start()].replace('-', '').replace(' ', '') or None
		correlativo = number_match[-1].group() or None
		return {'serie': serie, 'correlativo': correlativo}

	def button_annul(self):
		#self.button_cancel()
		#self.write({'annul': True, 'state': 'annul'})
		self.write({'auto_post': 'no', 'annul': True, 'state': 'cancel'})
		return True