from decimal import Decimal
from typing import Optional

from ..models import Treatment, Combo, Journey


def effective_price_for_treatment(treatment: Treatment) -> Optional[Decimal]:
    prices = []
    for zone_config in treatment.zone_configs.all():
        price = (
            zone_config.promotional_price
            if zone_config.promotional_price is not None
            else zone_config.price
        )
        if price is not None:
            prices.append(price)
    return min(prices) if prices else None


def effective_price_for_combo(combo: Combo) -> Optional[Decimal]:
    if combo.promotional_price is not None:
        return combo.promotional_price
    return combo.price


def effective_price_for_journey(journey: Journey) -> Optional[Decimal]:
    prices = []
    for treatment in journey.treatments.all():
        price = effective_price_for_treatment(treatment)
        if price is not None:
            prices.append(price)
    for combo in journey.combos.all():
        price = effective_price_for_combo(combo)
        if price is not None:
            prices.append(price)
    return min(prices) if prices else None


def effective_price_for_item(item):
    if isinstance(item, Treatment):
        return effective_price_for_treatment(item)
    if isinstance(item, Combo):
        return effective_price_for_combo(item)
    if isinstance(item, Journey):
        return effective_price_for_journey(item)
    return None
