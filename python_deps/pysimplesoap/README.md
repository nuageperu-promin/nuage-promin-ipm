# PySimpleSOAP 1.16.2 (ajustado para Python 3.12)

Copia de la versión pública **PySimpleSOAP 1.16.2** (LGPL 3.0, Mariano Reingart) con dos
cambios mínimos, necesarios porque Odoo.sh usa Python 3.12 y la versión de PyPI no se instala:

1. `pysimplesoap/transport.py`: `inspect.getargspec` (eliminado en Python 3.11) -> `inspect.getfullargspec`.
2. `setup.py`: ya no importa el paquete para leer la versión.

El comportamiento es idéntico a 1.16.2; es la versión que esperan los módulos `solse_pe_*`.
Se instala desde `requirements.txt` con `#subdirectory=python_deps/pysimplesoap`.
