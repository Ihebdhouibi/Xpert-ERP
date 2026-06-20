from decimal import Decimal

# Fixed VAT rate applied to all commercial transactions (labor, parts, services).
# Never sourced from the frontend — backend enforces this constant everywhere.
TVA_PCT: Decimal = Decimal("20")
