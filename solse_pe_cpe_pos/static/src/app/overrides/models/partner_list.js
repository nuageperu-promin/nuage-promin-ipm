/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { deserializeDateTime, deserializeDate, formatDateTime } from "@web/core/l10n/dates";
const { DateTime } = luxon;

import { PartnerList } from "@point_of_sale/app/screens/partner_list/partner_list";

var json_ordens = {}

patch(PartnerList.prototype, {
	
});
