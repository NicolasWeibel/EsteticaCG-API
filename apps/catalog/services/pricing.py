from decimal import Decimal
from typing import Optional, Tuple

from ..models import Treatment, Combo, Journey


def price_pair_for_treatment(treatment: Treatment) -> Tuple[Optional[Decimal], Optional[Decimal]]:
    best = None
    best_base = None
    for zone_config in treatment.zone_configs.all():
        effective = (
            zone_config.promotional_price
            if zone_config.promotional_price is not None
            else zone_config.price
        )
        base = zone_config.price
        if effective is None:
            continue
        if best is None or effective < best:
            best = effective
            best_base = base
    return best, best_base


def price_pair_for_combo(combo: Combo) -> Tuple[Optional[Decimal], Optional[Decimal]]:
    if combo.promotional_price is not None:
        return combo.promotional_price, combo.price
    return combo.price, combo.price


def price_pair_for_journey(journey: Journey) -> Tuple[Optional[Decimal], Optional[Decimal]]:
    best = None
    best_base = None
    for treatment in journey.treatments.all():
        effective, base = price_pair_for_treatment(treatment)
        if effective is None:
            continue
        if best is None or effective < best:
            best = effective
            best_base = base
    for combo in journey.combos.all():
        effective, base = price_pair_for_combo(combo)
        if effective is None:
            continue
        if best is None or effective < best:
            best = effective
            best_base = base
    return best, best_base


def effective_price_for_item(item):
    if isinstance(item, Treatment):
        return price_pair_for_treatment(item)[0]
    if isinstance(item, Combo):
        return price_pair_for_combo(item)[0]
    if isinstance(item, Journey):
        return price_pair_for_journey(item)[0]
    return None


def effective_price_for_treatment(treatment: Treatment) -> Optional[Decimal]:
    return price_pair_for_treatment(treatment)[0]


def effective_price_for_combo(combo: Combo) -> Optional[Decimal]:
    return price_pair_for_combo(combo)[0]


def effective_price_for_journey(journey: Journey) -> Optional[Decimal]:
    return price_pair_for_journey(journey)[0]


def average_duration_for_treatment(treatment: Treatment) -> Optional[float]:
    durations = [zc.duration for zc in treatment.zone_configs.all() if zc.duration]
    if not durations:
        return None
    return round(sum(durations) / len(durations), 2)


def duration_for_combo(combo: Combo) -> Optional[int]:
    return combo.duration


def duration_for_journey(journey: Journey) -> Optional[float]:
    durations = []
    for treatment in journey.treatments.all():
        avg = average_duration_for_treatment(treatment)
        if avg is not None:
            durations.append(avg)
    for combo in journey.combos.all():
        dur = duration_for_combo(combo)
        if dur is not None:
            durations.append(dur)
    return min(durations) if durations else None
