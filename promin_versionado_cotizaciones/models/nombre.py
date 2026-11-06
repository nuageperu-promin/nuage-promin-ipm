# -*- coding: utf-8 -*-
"""Reglas puras de numeración de versiones (sin dependencias de Odoo)."""
import re

_SUFIJO = re.compile(r'-V\d+$')


def nombre_base(nombre):
    """'S00123-V3' -> 'S00123'; 'S00123' -> 'S00123'."""
    return _SUFIJO.sub('', (nombre or '').strip())


def nombre_version(nombre, numero):
    """Número de una versión. La versión 1 conserva el número original.

    >>> nombre_version('S00123', 2)
    'S00123-V2'
    >>> nombre_version('S00123-V2', 3)
    'S00123-V3'
    >>> nombre_version('S00123-V2', 1)
    'S00123'
    """
    base = nombre_base(nombre)
    return base if numero <= 1 else '%s-V%d' % (base, numero)
