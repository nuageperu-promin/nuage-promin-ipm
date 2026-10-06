/** @odoo-module **/

import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import { patch } from "@web/core/utils/patch";

patch(OrderReceipt.prototype, {
	get receipt() {
		const receipt = super.receipt;
		
		// Agregar info personalizada si existe
		if (this.order.number) {
			receipt.numero_comprobante = this.order.number;
		}
		
		return receipt;
	}
});