#!/usr/bin/env python
# PySimpleSOAP 1.16.2 (PyPI) con ajuste de compatibilidad para Python >= 3.11 (Nuage).
# Diferencias frente a la versión pública 1.16.2:
#   - pysimplesoap/transport.py: inspect.getargspec -> inspect.getfullargspec
#   - setup.py: no importa el paquete para leer metadatos (el import fallaba en Python 3.12)
from setuptools import setup

setup(
    name='PySimpleSOAP',
    version='1.16.2',
    description='Python simple and lightweight SOAP Library',
    author='Mariano Reingart',
    author_email='reingart@gmail.com',
    url='https://github.com/pysimplesoap/pysimplesoap',
    packages=['pysimplesoap'],
    license='LGPL 3.0',
    classifiers=[
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
        "Topic :: Communications",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
