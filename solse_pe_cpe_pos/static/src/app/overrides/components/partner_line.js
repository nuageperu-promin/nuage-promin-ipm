/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PartnerLine } from "@point_of_sale/app/screens/partner_list/partner_line/partner_line";

/*
 * =============================================================================
 * FIX: OwlError "Cannot read properties of undefined (reading 'program_type')"
 * =============================================================================
 *
 * Bug nativo de pos_loyalty (Odoo 19) al abrir/cambiar de cliente:
 *
 *   - El dominio de carga de loyalty.card es `return False` (todas las cards).
 *   - El dominio de carga de loyalty.program filtra por: pos_ok, vigencia,
 *     max_usage, pricelist y pos_config_ids.
 *
 * Si un partner tiene una loyalty.card cuyo programa NO entra en ese filtro
 * (programa archivado, vencido, max_usage alcanzado, multi-POS de otro
 * config, pos_ok=False, etc.), la card se carga al cache pero su program_id
 * apunta a un loyalty.program que no está cargado.
 *
 * Resultado: pos.getLoyaltyCards(partner) devuelve la card huérfana, el XML
 * llama _getLoyaltyPointsRepr, y al hacer `program.program_type` revienta.
 *
 * Este patch defiende el punto donde explota: si el programa no está en el
 * cache, retornamos un fallback razonable en lugar de tirar la pantalla.
 *
 * Cuando se libere un fix oficial de Odoo este patch debería eliminarse.
 * =============================================================================
 */
patch(PartnerLine.prototype, {
    _getLoyaltyPointsRepr(loyaltyCard) {
        // Defensa: si el programa no está cargado en el cache del POS,
        // mostramos solo los puntos sin tipo (no podemos saber si es ewallet,
        // gift_card o loyalty), pero tampoco tiramos la pantalla.
        if (!loyaltyCard || !loyaltyCard.program_id) {
            const balance = (loyaltyCard && loyaltyCard.points) || 0;
            return `${balance.toFixed(2)} pts`;
        }
        return super._getLoyaltyPointsRepr(...arguments);
    },
});
