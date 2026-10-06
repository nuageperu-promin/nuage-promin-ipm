# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from base64 import b64decode, b64encode, encodebytes
from odoo.tools.float_utils import float_round
import xlsxwriter
import datetime
from io import StringIO, BytesIO
import logging
_logging = logging.getLogger(__name__)


DEFAULT_PLE_DATA = '%(month)s%(day)s%(sire_id)s%(report_03)s%(operacion)s%(contenido)s%(moneda)s%(sire)s'
DEFAULT_FORMAT_DICT = {
	'header_format': {
		'bold': True,
		'text_wrap': True,
		'valign': 'top',
		'fg_color': '#D7E4BC',
		'border': 1,
	},
	'text_format': {
		'num_format': '@',
	},
}

def get_last_day(day) :
	first_next = day.replace(day=28) + datetime.timedelta(days=4)
	return (first_next - datetime.timedelta(days=first_next.day))

def fill_name_data(name_dict) :
	common_data = {
		'month': '00',
		'day': '00',
		'report_03': '00',
		'operacion': '1',
		'contenido': '1',
		'moneda': '1',
		'sire': '1',
	}
	common_data_keys = list(common_data)
	for name in common_data_keys :
		if name in name_dict :
			del common_data[name]
	name_dict.update(common_data)

def number_to_ascii_chr(n) :
	try :
		n = int(n)
	except :
		n = 0
	digits = []
	if n > 0 :
		while n :
			digits.append(int(n % 26))
			n //= 26
	else :
		digits.append(0)
	digits = ''.join(chr(numero+65) for numero in digits[::-1])
	return digits