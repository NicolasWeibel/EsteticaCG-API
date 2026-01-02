from typing import Iterable, List, Optional, Dict, Tuple

from ..models import Treatment, Combo, Journey
from ..serializers import TreatmentSerializer, ComboSerializer, JourneySerializer
from .pricing import effective_price_for_item


SORT_OPTIONS = {
    "price_asc",
    "price_desc",
    "az",
    "za",
    "newest",
    "oldest",
    "manual",
}


def item_kind(item) -> Optional[str]:
    if isinstance(item, Treatment):
        return "treatment"
    if isinstance(item, Combo):
        return "combo"
    if isinstance(item, Journey):
        return "journey"
    return None


def item_key(item) -> Tuple[str, str]:
    return (item_kind(item), str(item.id))


def sort_items(
    items: Iterable,
    sort_key: str,
    order_map: Optional[Dict[Tuple[str, str], int]] = None,
) -> List:
    items_list = list(items)

    if sort_key == "manual":
        return _sort_manual(items_list, order_map or {})
    if sort_key == "price_asc":
        return _sort_by_price(items_list, reverse=False)
    if sort_key == "price_desc":
        return _sort_by_price(items_list, reverse=True)
    if sort_key == "az":
        return sorted(items_list, key=lambda obj: (obj.title or "").lower())
    if sort_key == "za":
        return sorted(items_list, key=lambda obj: (obj.title or "").lower(), reverse=True)
    if sort_key == "newest":
        return sorted(items_list, key=lambda obj: obj.created_at, reverse=True)
    if sort_key == "oldest":
        return sorted(items_list, key=lambda obj: obj.created_at)
    return _sort_by_price(items_list, reverse=False)


def serialize_items(items: Iterable, context=None) -> List[dict]:
    data = []
    for item in items:
        if isinstance(item, Treatment):
            data.append(TreatmentSerializer(item, context=context).data)
        elif isinstance(item, Combo):
            data.append(ComboSerializer(item, context=context).data)
        elif isinstance(item, Journey):
            data.append(JourneySerializer(item, context=context).data)
    return data


def _sort_manual(items, order_map):
    with_order = []
    without_order = []
    for item in items:
        key = item_key(item)
        if key in order_map:
            with_order.append(item)
        else:
            without_order.append(item)
    with_order.sort(key=lambda obj: order_map[item_key(obj)])
    without_order.sort(key=lambda obj: (obj.title or "").lower())
    return with_order + without_order


def _sort_by_price(items, reverse=False):
    with_price = []
    without_price = []
    for item in items:
        price = effective_price_for_item(item)
        if price is None:
            without_price.append(item)
        else:
            with_price.append((price, item))
    with_price.sort(key=lambda pair: pair[0], reverse=reverse)
    sorted_items = [item for _, item in with_price]
    return sorted_items + without_price
