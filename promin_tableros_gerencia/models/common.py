def factor_sql(fecha, moneda, compania):
    """Fragmento SQL (CROSS JOIN LATERAL) que deja el factor para convertir a USD
    al tipo de cambio de la fecha dada (o el más cercano si no hay uno anterior)."""
    return """
LEFT JOIN res_currency usd ON usd.name = 'USD'
CROSS JOIN LATERAL (
    SELECT CASE
        WHEN {m} = usd.id THEN 1.0
        ELSE COALESCE((
                SELECT r.rate FROM res_currency_rate r
                WHERE r.currency_id = usd.id
                  AND (r.company_id = {c} OR r.company_id IS NULL)
                ORDER BY (r.name <= {f}) DESC, ABS(r.name - {f})
                LIMIT 1), 1.0)
             / COALESCE((
                SELECT r2.rate FROM res_currency_rate r2
                WHERE r2.currency_id = {m}
                  AND (r2.company_id = {c} OR r2.company_id IS NULL)
                ORDER BY (r2.name <= {f}) DESC, ABS(r2.name - {f})
                LIMIT 1), 1.0)
    END AS factor
) k
""".format(m=moneda, c=compania, f=fecha)


SECTOR_SQL = """
    CASE
        WHEN p.promin_sector IS NOT NULL THEN p.promin_sector
        WHEN co.code IS NOT NULL AND co.code <> 'PE' THEN 'exterior'
        ELSE 'privado'
    END"""

SECTORES = [('privado', 'Privado'), ('estado', 'Estado'), ('exterior', 'Exterior')]
