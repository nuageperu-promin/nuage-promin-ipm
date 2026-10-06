# -*- coding: utf-8 -*-

from odoo import models, api
import logging
_logger = logging.getLogger(__name__)


class LatamDocumentType(models.Model):
	_name = 'l10n_latam.document.type'
	_inherit = ['l10n_latam.document.type', 'pos.load.mixin']

	@api.model
	def _load_pos_data_fields(self, config):
		return ['id', 'name', 'code', 'country_id', 'report_name', 'internal_type', 'nota_credito', 'nota_debito']
	
	@api.model
	def _load_pos_data_domain(self, data, config):
		# Cargar los tipos de documento configurados en el POS
		if config and hasattr(config, 'documento_venta_ids'):
			return [('id', 'in', config.documento_venta_ids.ids)]
		return [('country_id.code', '=', 'PE')]


class LatamIdentificationType(models.Model):
	_name = 'l10n_latam.identification.type'
	_inherit = ['l10n_latam.identification.type', 'pos.load.mixin']

	@api.model
	def _load_pos_data_fields(self, config):
		return ['id', 'name', 'l10n_pe_vat_code', 'sequence']
	
	@api.model
	def _load_pos_data_domain(self, data, config):
		return [('country_id.code', '=', 'PE')]


class AccountPaymentTerm(models.Model):
	_name = 'account.payment.term'
	_inherit = ['account.payment.term', 'pos.load.mixin']

	@api.model
	def _load_pos_data_fields(self, config):
		return ['id', 'name', 'display_name']
	
	@api.model
	def _load_pos_data_domain(self, data, config):
		return []


class ResCity(models.Model):
	_name = 'res.city'
	_inherit = ['res.city', 'pos.load.mixin']

	@api.model
	def _load_pos_data_fields(self, config):
		return ['id', 'name', 'state_id']
	
	@api.model
	def _load_pos_data_domain(self, data, config):
		return [('country_id.code', '=', 'PE')]


class L10nPeResCityDistrict(models.Model):
	_name = 'l10n_pe.res.city.district'
	_inherit = ['l10n_pe.res.city.district', 'pos.load.mixin']

	@api.model
	def _load_pos_data_fields(self, config):
		return ['id', 'name', 'city_id', 'code']
	
	@api.model
	def _load_pos_data_domain(self, data, config):
		return []


class PosSession(models.Model):
	_inherit = 'pos.session'

	@api.model
	def _load_pos_data_models(self, config):
		"""Extender modelos cargados en el POS para incluir datos peruanos"""
		result = super()._load_pos_data_models(config)
		
		# Agregar modelos peruanos necesarios
		modelos_peruanos = [
			'l10n_latam.document.type',
			'l10n_latam.identification.type',
			'account.payment.term',
			'res.city',
			'l10n_pe.res.city.district',
		]
		
		result.extend(modelos_peruanos)
		return result