# nuage_vendor_evaluation — instalación en PROMIN (Odoo.sh)

El módulo llega con el código de la rama `main` del repositorio.

1. Tras el despliegue de `main`, entrar a Odoo con el modo desarrollador activado.
2. Aplicaciones → **Actualizar lista de aplicaciones**.
3. Quitar el filtro «Aplicaciones», buscar **Evaluación de Proveedores** e **Instalar**.
   Requiere los módulos estándar Compras (`purchase`), `purchase_stock` y `mail` (ya instalados en PROMIN).

Menú: Compras → Evaluación de proveedores. Criterios: Compras → Configuración → Criterios de evaluación.
Para actualizar en el futuro: Aplicaciones → buscar el módulo → **Actualizar**.
