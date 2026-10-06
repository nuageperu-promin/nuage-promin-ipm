/** @odoo-module **/

import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

patch(TicketScreen.prototype, {
	async _onDoRefund() {
		const order = this.getSelectedSyncedOrder();

		if (this._doesOrderHaveSoleItem(order)) {
			if (!this._prepareAutoRefundOnOrder(order)) {
				return;
			}
		}

		if (!order) {
			this._state.ui.highlightHeaderNote = !this._state.ui.highlightHeaderNote;
			return;
		}

		let doc_n_credito = order.get_doc_type_sale();
		let doc_venta = this.env.pos.get_doc_type_sale_id(doc_n_credito);
		
		if(!doc_venta) {
			this.dialog.add(AlertDialog, {
				title: 'Aviso',
				body: 'No se encontro el tipo de documento',
			});
			return this.render();
		}
		
		let nota_credito = doc_venta.nota_credito;
		if(!nota_credito) {
			this.dialog.add(AlertDialog, {
				title: 'Aviso',
				body: 'Establezca un tipo de comprobante para la nota de crédito',
			});
			return this.render();
		}

		const partner = order.get_partner();
		const allToRefundDetails = this._getRefundableDetails(partner);
		
		if (allToRefundDetails.length == 0) {
			this._state.ui.highlightHeaderNote = !this._state.ui.highlightHeaderNote;
			return;
		}

		const destinationOrder =
			this.props.destinationOrder && partner === this.props.destinationOrder.get_partner()
				? this.props.destinationOrder
				: this._getEmptyOrder(partner);

		for (const refundDetail of allToRefundDetails) {
			const product = this.env.pos.db.get_product_by_id(refundDetail.orderline.productId);
			const options = this._prepareRefundOrderlineOptions(refundDetail);
			await destinationOrder.add_product(product, options);
			refundDetail.destinationOrderUid = destinationOrder.uid;
		}

		if (partner && !destinationOrder.get_partner()) {
			destinationOrder.set_partner(partner);
			destinationOrder.updatePricelist(partner);
		}

		if (this.env.pos.get_order().cid !== destinationOrder.cid) {
			this.env.pos.set_order(destinationOrder);
		}
		
		destinationOrder.set_l10n_latam_document_type(nota_credito[0]);
		this._onCloseScreen();
	}
});