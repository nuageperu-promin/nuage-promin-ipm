# PySimpleSOAP 1.16.2 (ajustado para Python 3.12)

Copia de la versión pública **PySimpleSOAP 1.16.2** (LGPL 3.0, Mariano Reingart) con dos
cambios mínimos, necesarios porque Odoo.sh usa Python 3.12 y la versión de PyPI no se instala:

1. `pysimplesoap/transport.py`: `inspect.getargspec` (eliminado en Python 3.11) -> `inspect.getfullargspec`.
2. `setup.py`: ya no importa el paquete para leer la versión.
3. `pysimplesoap/transport.py`: las versiones de httplib2 se comparaban como texto (`"0.20.4" <= "0.7.7"` daba verdadero) y se aplicaba un parche de 2012 que rompía toda conexión HTTPS (`fixer() missing 3 required positional arguments`). Ahora se comparan numéricamente.

El comportamiento es idéntico a 1.16.2; es la versión que esperan los módulos `solse_pe_*`.
Se instala desde `requirements.txt` con `#subdirectory=python_deps/pysimplesoap`.
