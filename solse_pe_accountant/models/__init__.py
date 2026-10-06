# -*- coding: utf-8 -*-

from . import res_company
from . import res_config_settings
from . import res_partner
from . import account_account
from . import account_move
from . import tipo_cambio_sunat
# account_payment_term eliminado: contenía 4 funciones huérfanas que nunca se
# llamaban desde Odoo ni desde otro punto del módulo. Además, su código no
# compilaba (variables como company_currency, total_amount, tax_amount_left,
# total_balance se referenciaban sin estar definidas en scope).
