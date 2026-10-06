# Changelog v19.0.0.12

## Hotfix

Corregido `NameError: name 'AccountMove' is not defined` en
`models/tipo_cambio_sunat.py:205`, dentro del refactor de
`_recompute_cash_rounding_lines` aplicado en v19.0.0.11.

El override usaba `super(AccountMove, self)` cuando la clase en ese archivo
en realidad se llama `AccountMoveSunat`. Fix de 1 línea:

```python
# Antes (v19.0.0.11):
return super(AccountMove, self)._recompute_cash_rounding_lines()

# Después (v19.0.0.12):
return super(AccountMoveSunat, self)._recompute_cash_rounding_lines()
```

El error solo se disparaba al ejecutar la rama "delega al super" del
refactor, es decir, en facturas en moneda local (PEN→PEN) o documentos
fuera de `INCLUIDOS`. Como ese path es el más común, se manifestó pronto.

### Recomendación de estilo

Para evitar este tipo de error en el futuro, conviene migrar
progresivamente los `super(NombreClase, self)` a `super()` (forma
idiomática en Python 3, no requiere acordarse del nombre de la clase).
Pendiente para una limpieza posterior, no se aplica en este hotfix para
mantener el cambio mínimo.
