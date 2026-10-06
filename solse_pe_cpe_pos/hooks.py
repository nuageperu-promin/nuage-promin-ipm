# -*- coding: utf-8 -*-

"""
post_migrate hook de solse_farmacia.
Recomputa campos stored con NULL en BD tras actualización del módulo.
"""
import logging
_logger = logging.getLogger(__name__)

def post_init_hook(env):
	_activar_receipt_correcto(env)

def post_load_hook(env):
	_activar_receipt_correcto(env)

def _activar_receipt_correcto(env):
	pe_instalado = env['ir.module.module'].search_count([
		('name', '=', 'solse_pe_cpe_pos'),
		('state', '=', 'installed'),
	]) > 0

	env['ir.asset'].sudo().search([
		('name', '=', 'solse_farmacia receipt standalone')
	]).write({'active': not pe_instalado})

	env['ir.asset'].sudo().search([
		('name', '=', 'solse_farmacia receipt PE override')
	]).write({'active': pe_instalado})
	
