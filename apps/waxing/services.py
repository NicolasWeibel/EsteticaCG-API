from collections.abc import Iterable

from .models import Area, AreaCategory, FeaturedItemOrder, Pack
from .models.choices import PackPosition, SortOption


def image_url(image_field):
    if image_field:
        try:
            return image_field.url
        except Exception:
            return None
    return None


def _price_pair(item):
    base_price = item.price
    effective_price = (
        item.promotional_price if item.promotional_price is not None else base_price
    )
    return effective_price, base_price


def sort_items(items: Iterable, sort_key: str):
    items_list = list(items)
    if sort_key == SortOption.MANUAL:
        return sorted(
            items_list,
            key=lambda obj: (
                obj.order,
                -(obj.created_at.timestamp() if getattr(obj, "created_at", None) else 0),
                (obj.name or "").lower(),
            ),
        )
    if sort_key == SortOption.PRICE_ASC:
        return sorted(
            items_list,
            key=lambda obj: (_price_pair(obj)[0], (obj.name or "").lower()),
        )
    if sort_key == SortOption.PRICE_DESC:
        return sorted(
            items_list,
            key=lambda obj: (-_price_pair(obj)[0], (obj.name or "").lower()),
        )
    if sort_key == SortOption.AZ:
        return sorted(items_list, key=lambda obj: (obj.name or "").lower())
    if sort_key == SortOption.ZA:
        return sorted(items_list, key=lambda obj: (obj.name or "").lower(), reverse=True)
    return sorted(
        items_list,
        key=lambda obj: (
            obj.order,
            -(obj.created_at.timestamp() if getattr(obj, "created_at", None) else 0),
            (obj.name or "").lower(),
        ),
    )


def serialize_area(area: Area, show_prices: bool = True):
    effective_price, base_price = _price_pair(area)
    return {
        "kind": "area",
        "id": area.id,
        "section_id": area.section_id,
        "category_id": area.category_id,
        "name": area.name,
        "price": effective_price if show_prices else None,
        "price_without_discount": base_price if show_prices else None,
        "duration": area.duration,
        "short_description": area.short_description,
        "description": area.description,
        "image": image_url(area.image),
        "is_featured": area.is_featured,
        "order": area.order,
    }


def serialize_pack(pack: Pack, show_prices: bool = True):
    effective_price, base_price = _price_pair(pack)
    return {
        "kind": "pack",
        "id": pack.id,
        "section_id": pack.section_id,
        "name": pack.name,
        "price": effective_price if show_prices else None,
        "price_without_discount": base_price if show_prices else None,
        "duration": pack.duration,
        "short_description": pack.short_description,
        "description": pack.description,
        "image": image_url(pack.image),
        "is_featured": pack.is_featured,
        "order": pack.order,
    }


def serialize_category(
    category: AreaCategory,
    *,
    areas: list[Area],
    packs: list[Pack],
    show_prices: bool = True,
):
    area_items = [serialize_area(area, show_prices=show_prices) for area in areas]
    pack_items = [serialize_pack(pack, show_prices=show_prices) for pack in packs]
    if category.pack_position == PackPosition.FIRST:
        items = pack_items + area_items
    else:
        items = area_items + pack_items

    return {
        "id": category.id,
        "section_id": category.section_id,
        "name": category.name,
        "short_description": category.short_description,
        "description": category.description,
        "image": image_url(category.image),
        "order": category.order,
        "show_packs": category.show_packs,
        "area_sort": category.area_sort,
        "pack_sort": category.pack_sort,
        "pack_position": category.pack_position,
        "items": items,
    }


def single_category_packs_for_category(category: AreaCategory):
    packs = (
        Pack.objects.filter(section=category.section, is_active=True)
        .prefetch_related("pack_areas__area")
        .all()
    )
    eligible = []
    for pack in packs:
        category_ids = {pack_area.area.category_id for pack_area in pack.pack_areas.all()}
        if len(category_ids) == 1 and category.id in category_ids:
            eligible.append(pack)
    return eligible


def sort_featured_items(section, sort_key: str):
    areas = section.areas.filter(is_active=True, is_featured=True)
    packs = section.packs.filter(is_active=True, is_featured=True)
    mixed = [("area", area) for area in areas] + [("pack", pack) for pack in packs]

    if sort_key == SortOption.MANUAL:
        order_map = {
            (row.item_kind, str(row.item_id)): row.order
            for row in FeaturedItemOrder.objects.filter(section=section)
        }
        with_order = []
        without_order = []
        for kind, item in mixed:
            key = (kind, str(item.id))
            if key in order_map:
                with_order.append(
                    (
                        order_map[key],
                        -(item.created_at.timestamp() if getattr(item, "created_at", None) else 0),
                        (item.name or "").lower(),
                        kind,
                        item,
                    )
                )
            else:
                without_order.append(
                    (
                        -(item.created_at.timestamp() if getattr(item, "created_at", None) else 0),
                        (item.name or "").lower(),
                        kind,
                        item,
                    )
                )
        with_order.sort(key=lambda data: (data[0], data[1], data[2]))
        without_order.sort(key=lambda data: (data[0], data[1]))
        return [(kind, item) for _, _, _, kind, item in with_order] + [
            (kind, item) for _, _, kind, item in without_order
        ]

    if sort_key == SortOption.PRICE_ASC:
        return sorted(
            mixed,
            key=lambda data: (_price_pair(data[1])[0], (data[1].name or "").lower()),
        )
    if sort_key == SortOption.PRICE_DESC:
        return sorted(
            mixed,
            key=lambda data: (-_price_pair(data[1])[0], (data[1].name or "").lower()),
        )
    if sort_key == SortOption.ZA:
        return sorted(mixed, key=lambda data: (data[1].name or "").lower(), reverse=True)

    return sorted(mixed, key=lambda data: (data[1].name or "").lower())
