# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import requests
import pytz

import datetime
import logging
_logger = logging.getLogger(__name__)
tz = pytz.timezone('America/Lima')

class ResCurrency(models.Model):
	_inherit = 'res.currency'

	rate_type = fields.Selection([
		('compra', 'Compra'),
		('venta', 'Venta'),
	], string='Tipo de cambio', default='compra')

	_unique_name = models.Constraint(
		'unique (name, rate_type)',
		"The currency code must be unique!",
	)

	# A-16: name_get no existe en Odoo 19; el reemplazo es _compute_display_name.
	@api.depends('name', 'rate_type')
	def _compute_display_name(self):
		etiquetas = dict(self._fields['rate_type'].selection)
		for currency in self:
			if currency.rate_type:
				currency.display_name = '%s / %s' % (
					currency.name, etiquetas.get(currency.rate_type, ''))
			else:
				currency.display_name = currency.name

	def crear_linea_tipo_cambio(self, datos):
		try:
			self.env['res.currency.rate'].create(datos)
		except Exception as e:
			_logger.info("error al crear la taza de cambio para este día")
			_logger.info(e)

	def update_exchange_rate_migo(self, token, fecha):
		token = self.env.company.token_api
		url = "https://api.migo.pe/api/v1/exchange/date"

		record = self.with_context(tz=pytz.timezone('America/Lima'))
		if not fecha:
			fecha = fields.Datetime.to_string(fields.Datetime.context_timestamp(record, datetime.datetime.now()))
			fecha = datetime.datetime.strptime(str(fecha), "%Y-%m-%d %H:%M:%S").date().strftime("%Y-%m-%d")
		else:
			fecha = datetime.datetime.strptime(str(fecha), "%Y-%m-%d").date().strftime("%Y-%m-%d")

		payload = {
			"token": token,
			"fecha": fecha
		}

		headers = {
			"Accept": "application/json",
			"Content-Type": "application/json"
		}

		response = requests.post(url, json=payload, headers=headers, timeout=10).json()

		if not token:
			raise ValidationError('Token no encontrado')

		if not response['success']:
			return

		usd_venta = self.env['res.currency'].search([('name', '=', 'USD'), ('rate_type', '=', 'venta')], limit=1)
		
		#fecha = fields.Date.context_today(self)
		if usd_venta:
			inverse_company_rate = response['precio_venta']
			data_sale = {
				'name': fecha,
				'rate': 1 / float(inverse_company_rate),
				'inverse_company_rate': response['precio_venta'],
				'currency_id': usd_venta.id
			}
			moneda = self.env['res.currency.rate'].search([('name', '=', fecha), ('currency_id', '=', usd_venta.id), ('company_id', '=', self.env.company.id)])
			if moneda:
				moneda.write(data_sale)
			else:
				self.crear_linea_tipo_cambio(data_sale)
		usd_compra = self.env['res.currency'].search([('name', '=', 'USD'), ('rate_type', '=', 'compra')], limit=1)

		if usd_compra:
			inverse_company_rate = response['precio_compra']
			data_purchase = {
				'name': fecha,
				'rate': 1 / float(inverse_company_rate),
				'inverse_company_rate': response["precio_compra"],
				'currency_id': usd_compra.id
			}
			moneda = self.env['res.currency.rate'].search([('name', '=', fecha), ('currency_id', '=', usd_compra.id), ('company_id', '=', self.env.company.id)])
			if moneda:
				moneda.write(data_purchase)
			else:
				self.crear_linea_tipo_cambio(data_purchase)

	def update_exchange_rate_apidev(self, token, fecha):
		token = self.env.company.token_api

		if not fecha:
			fecha = datetime.datetime.today().strftime('%Y-%m-%d')
		else:
			fecha = datetime.datetime.strptime(str(fecha), "%Y-%m-%d").date().strftime("%Y-%m-%d")

		url = "https://apiperu.dev/api/tipo_de_cambio"
		payload = {
			"token": token,
			"fecha": fecha
		}


		headers = {
			"Authorization": "Bearer %s" % token,
			"Content-Type": "application/json",
			"Accept": "application/json",
		}

		response = requests.post(url, json=payload, headers=headers, timeout=10).json()
		if not token:
			raise ValidationError('Token no encontrado')

		if not response['success']:
			return

		response = response['data']

		usd_venta = self.env['res.currency'].search(
			[('name', '=', 'USD'), ('rate_type', '=', 'venta')], limit=1)
		if usd_venta:
			inverse_company_rate = response['venta']
			data_sale = {
				'name': fields.Date.context_today(self),
				'company_rate': 1 / float(inverse_company_rate),
				'rate': 1 / float(inverse_company_rate),
				'inverse_company_rate': response['venta'],
				'currency_id': usd_venta.id,
				'company_id': self.env.company.id
			}
			moneda = self.env['res.currency.rate'].search([('name', '=', fecha), ('currency_id', '=', usd_venta.id), ('company_id', '=', self.env.company.id)])
			if moneda:
				moneda.write(data_sale)
			else:
				self.crear_linea_tipo_cambio(data_sale)
		usd_compra = self.env['res.currency'].search(
			[('name', '=', 'USD'), ('rate_type', '=', 'compra')], limit=1)

		if usd_compra:
			inverse_company_rate = response['compra']
			data_purchase = {
				'name': fields.Date.context_today(self),
				'company_rate': 1 / float(inverse_company_rate),
				'rate': 1 / float(inverse_company_rate),
				'inverse_company_rate': response["compra"],
				'currency_id': usd_compra.id,
				'company_id': self.env.company.id
			}
			moneda = self.env['res.currency.rate'].search([('name', '=', fecha), ('currency_id', '=', usd_compra.id), ('company_id', '=', self.env.company.id)])
			if moneda:
				moneda.write(data_purchase)
			else:
				self.crear_linea_tipo_cambio(data_purchase)
			

	def update_exchange_rate(self, fecha):
		token = ''
		tipo_busqueda = 'apiperu'
		if self.env.company:
			token = self.env.company.token_api
			tipo_busqueda = self.env.company.busqueda_ruc_dni
		else:
			token = self.env.company.token_api
			tipo_busqueda = self.env.company.busqueda_ruc_dni

		if tipo_busqueda == 'apimigo':
			self.update_exchange_rate_migo(token, fecha)
		else:
			self.update_exchange_rate_apidev(token, fecha)


	def tp_actualizar_tipo_cambio(self, fecha):
		companies = self.env['res.company'].search([])
		token = ''
		tipo_busqueda = 'apiperu'
		for company in companies:
			company_self = self.with_company(company)
			token = company.token_api
			if not token:
				continue
			tipo_busqueda = company.busqueda_ruc_dni
			
			try:
				if tipo_busqueda == 'apimigo':
					company_self.update_exchange_rate_migo(token, fecha)
				else:
					company_self.update_exchange_rate_apidev(token, fecha)
			except Exception as e:
				_logger.info("ocurrio un error al actulizar el tipo de cambio por tarea programada")
				_logger.info(e)
		

	@api.model
	def auto_update(self):
		self.update_exchange_rate(False)

	def auto_update_simple(self):
		self.update_exchange_rate(False)


class CurrencyRate(models.Model):
	_inherit = "res.currency.rate"

	def actualizar_tc(self):
		self.currency_id.update_exchange_rate(self.name)

