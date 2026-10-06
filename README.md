# nuage-promin-ipm

Repositorio de módulos de Odoo 19 Enterprise para **Proveedores Mineros S.A.C.** e
**Industria Proveedores Mineros S.C.R.L.**, mantenido por **Nuage Perú S.A.C.**

Repositorio privado y de uso exclusivo para este proyecto.

## Qué contiene

Todos los módulos viven como carpetas independientes en la raíz del repositorio
(sin subcarpetas agrupadoras), para que Odoo.sh los detecte automáticamente al
agregar este repositorio como submódulo. La organización se da por el **prefijo**
del nombre, no por carpetas:

| Prefijo | Contenido |
|---|---|
| `solse_pe_*` | Módulos de localización peruana (facturación electrónica, PLE, SIRE, Compras y Contabilidad) y de Nómina Perú (planilla, asistencia, PLAME) |
| `promin_*` | Desarrollos hechos a medida para este proyecto |

## Convención de ramas

| Rama | Uso |
|---|---|
| `main` | Rama estable. Es la que se reporta a Odoo.sh como "rama a desplegar". |
| `develop` | Rama de trabajo activo. Los desarrollos nuevos se integran aquí antes de pasar a `main`. |

## Estado de los Desarrollos

| Módulo | Estado |
|---|---|
| `promin_bimoneda_pen_usd` | Pendiente de especificación |
| `promin_pedidos_vs_facturacion` | Pendiente de especificación |
| `promin_trazabilidad_compras` | Pendiente de especificación |
| `promin_control_obligaciones_financieras` | Pendiente de especificación |
| `promin_asiento_cierre_contable` | Pendiente de especificación |
| `promin_libros_electronicos_pe` | Pendiente de especificación |
| `promin_libro_activo_fijo` | Pendiente de especificación |
| `promin_gestion_ubicaciones_almacen` | Pendiente de especificación |
| `promin_rentabilidad_lote_capa2` | Pendiente de especificación |

## Integración con Odoo.sh (submódulo)

Datos que TI de Proveedores Mineros necesita para configurar el submódulo en Odoo.sh:

- **URL SSH del repositorio:** `git@github.com:nuageperu-promin/nuage-promin-ipm.git`
- **Rama a desplegar:** `main`

### Flujo de trabajo acordado con TI de PROMIN (05/10/2026)

1. Nuage pone el repositorio en **Público** temporalmente para la carga inicial.
2. PROMIN lo agrega como submódulo en el entorno *develop* de Odoo.sh.
3. Nuage vuelve a poner el repositorio en **Privado**.
4. PROMIN envía a Nuage la **Deploy Key** generada por Odoo.sh; Nuage la agrega en
   GitHub (Settings > Deploy keys) para habilitar despliegues futuros de forma segura.
5. Toda actualización posterior de un módulo se comunica a PROMIN por correo,
   detallando el motivo y los datos a actualizar en Odoo.sh.

## Actualizaciones

Ver `CHANGELOG.md` para el historial de versiones y correcciones recibidas o
desarrolladas para cada módulo.

## Requisitos

Ver `requirements.txt` para dependencias de Python (se completa a medida que cada
módulo lo requiera).
