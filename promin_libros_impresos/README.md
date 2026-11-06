# promin_libros_impresos

**Desarrollo:** Libro Diario (Formato 5.1) y Libro Mayor (Formato 6.1) **impresos** en PDF, estilo clásico, según los modelos entregados por PROMIN.

No reemplaza a los libros electrónicos PLE (TXT para SUNAT): usa la misma lógica de libro, CUO y correlativo para que ambos coincidan.

## Uso
Contabilidad → Reportes → **Libros contables impresos** → Libro Diario (5.1) o Libro Mayor (6.1).
Se elige el período (por defecto, el mes anterior), el folio inicial, y opcionalmente solo algunas cuentas
(por prefijo, p. ej. `10,12,70`). El PDF se abre en una pestaña nueva, listo para imprimir (A4 horizontal).

## Reglas
* Solo asientos **publicados** de la compañía elegida.
* **Libro (Tabla 8):** por diario. Bancos y caja = 01, compras = 08, ventas = 14, otros = 05.
  Se puede forzar en el diario (campo «Libro en impresos»).
* **Vou:** correlativo por libro y período, ordenado por fecha y número de asiento. Es el mismo en Diario y Mayor.
* **C.U.O.:** número del asiento.
* **Doc. Sustent.:** serie-número del comprobante (en pagos, el del comprobante que cancelan).
* **Diario:** páginas con VIENEN/VAN y TOTALES GENERALES. Un asiento no se parte entre páginas.
* **Mayor:** por cuenta, con SALDO ANTERIOR, saldo corrido, TOTAL por cuenta y TOTALES GENERALES.
  Saldo anterior: cuentas 1-5 acumulado histórico; cuentas 6-9 solo desde el 1 de enero del año.

## Prueba
`python3 tests/test_modelos.py <Libro_Diario.pdf> <Libro_Mayor.pdf> [carpeta]` reconstruye los modelos de PROMIN
y verifica páginas, VAN, totales y saldos.
