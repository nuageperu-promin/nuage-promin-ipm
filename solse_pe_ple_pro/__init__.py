# -*- coding: utf-8 -*-

from . import models


def post_init_hook(env):
	"""
	Hook ejecutado automáticamente después de instalar o actualizar el módulo.

	Inicializa los flags is_cash_account / is_bank_account en todas las cuentas
	existentes del plan contable, detectando cuentas de efectivo (10X) y banco
	(104X) por el prefijo PCGE. Es idempotente.

	Sin este hook, las cuentas cargadas por el plan contable nativo de Odoo o
	importadas en masa quedarían con los flags en False, haciendo que el
	Libro Caja y Bancos (PLE 01) genere archivos vacíos.
	"""
	env['account.account']._solse_ple_init_caja_banco_flags()
from . import wizard
