import uuid
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.waxing.models import (
    Area,
    AreaCategory,
    FeaturedItemOrder,
    Pack,
    PackArea,
    Section,
    WaxingContent,
    WaxingSettings,
)
from apps.waxing.models.choices import SortOption


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _staff_user():
    User = get_user_model()
    return User.objects.create_user(
        email=f"{_uid('staff')}@test.com",
        password="test1234",
        is_staff=True,
        is_active=True,
    )


def _create_section(name: str, **kwargs) -> Section:
    defaults = {"is_active": True}
    defaults.update(kwargs)
    return Section.objects.create(name=name, **defaults)


def _create_category(section: Section, **kwargs) -> AreaCategory:
    defaults = {
        "name": _uid("cat"),
        "order": 0,
        "is_active": True,
        "show_packs": True,
        "area_sort": SortOption.MANUAL,
        "pack_sort": SortOption.MANUAL,
    }
    defaults.update(kwargs)
    return AreaCategory.objects.create(section=section, **defaults)


def _create_area(section: Section, category: AreaCategory, **kwargs) -> Area:
    defaults = {
        "name": _uid("area"),
        "price": 1000,
        "category": category,
        "section": section,
        "is_active": True,
        "order": 0,
    }
    defaults.update(kwargs)
    return Area.objects.create(**defaults)


def _create_pack(section: Section, **kwargs) -> Pack:
    defaults = {
        "name": _uid("pack"),
        "price": 5000,
        "section": section,
        "is_active": True,
        "order": 0,
    }
    defaults.update(kwargs)
    return Pack.objects.create(**defaults)


@pytest.mark.django_db
def test_public_endpoint_contract():
    client = APIClient()
    mujer = _create_section("mujer", featured_sort=SortOption.MANUAL)
    hombre = _create_section("hombre", featured_sort=SortOption.AZ)

    cat_mujer = _create_category(mujer, name="Piernas", order=0)
    cat_hombre = _create_category(hombre, name="Torso", order=0)

    area_featured = _create_area(
        mujer,
        cat_mujer,
        name="Axilas",
        price=8000,
        promotional_price=7000,
        duration=25,
        is_featured=True,
    )
    _create_area(hombre, cat_hombre, name="Pecho", price=9000)
    pack_featured = _create_pack(
        mujer,
        name="Pack Premium",
        price=15000,
        promotional_price=12000,
        duration=60,
        is_featured=True,
    )
    PackArea.objects.create(pack=pack_featured, area=area_featured)

    content = WaxingContent.objects.order_by("-created_at").first()
    content.title = "Sobre depilacion"
    content.description = "Descripcion extensa"
    content.save()
    content.benefits.create(title="Duracion", detail="Mayor duracion", order=0)
    content.recommendations.create(title="Hidratar", detail="Usar crema", order=0)
    content.faqs.create(question="Duele?", answer="Depende de la zona", order=0)

    response = client.get("/api/v1/waxing/")
    assert response.status_code == 200
    assert set(response.data.keys()) == {
        "category",
        "genders",
        "sections_by_gender",
        "featured_by_gender",
        "content",
    }
    assert response.data["category"] == "waxing"
    assert set(response.data["genders"]) == {"mujer", "hombre"}
    featured_mujer = response.data["featured_by_gender"]["mujer"]
    assert {item["kind"] for item in featured_mujer} == {"area", "pack"}
    featured_by_name = {item["name"]: item for item in featured_mujer}
    assert featured_by_name["Axilas"]["duration"] == 25
    assert featured_by_name["Pack Premium"]["duration"] == 60
    assert featured_by_name["Axilas"]["price"] == 7000
    assert featured_by_name["Axilas"]["price_without_discount"] == 8000
    assert "promotional_price" not in featured_by_name["Axilas"]
    assert featured_by_name["Pack Premium"]["price"] == 12000
    assert featured_by_name["Pack Premium"]["price_without_discount"] == 15000
    assert "promotional_price" not in featured_by_name["Pack Premium"]
    category_items = response.data["sections_by_gender"]["mujer"]["categories"][0]["items"]
    items_by_name = {item["name"]: item for item in category_items}
    assert items_by_name["Axilas"]["price"] == 7000
    assert items_by_name["Axilas"]["price_without_discount"] == 8000
    assert "promotional_price" not in items_by_name["Axilas"]
    assert items_by_name["Pack Premium"]["price"] == 12000
    assert items_by_name["Pack Premium"]["price_without_discount"] == 15000
    assert "promotional_price" not in items_by_name["Pack Premium"]
    assert response.data["content"]["title"] == "Sobre depilacion"
    assert "image" in response.data["content"]
    assert "benefits_image" in response.data["content"]
    assert "recommendations_image" in response.data["content"]


@pytest.mark.django_db
def test_public_filter_by_gender_keeps_full_structure():
    client = APIClient()
    mujer = _create_section("mujer")
    hombre = _create_section("hombre")
    cat_mujer = _create_category(mujer, name="Rostro")
    cat_hombre = _create_category(hombre, name="Espalda")
    _create_area(mujer, cat_mujer, name="Bozo")
    _create_area(hombre, cat_hombre, name="Espalda alta")

    response = client.get("/api/v1/waxing/?section=mujer")
    assert response.status_code == 200
    assert response.data["sections_by_gender"]["mujer"]["section"]["name"] == "mujer"
    assert response.data["sections_by_gender"]["hombre"] == {}
    assert response.data["featured_by_gender"]["hombre"] == []


@pytest.mark.django_db
def test_public_hides_price_and_price_without_discount_when_show_prices_is_false():
    client = APIClient()
    section = _create_section("mujer")
    category = _create_category(section, name="Piernas")
    area = _create_area(
        section,
        category,
        name="Axilas",
        price=8000,
        promotional_price=7000,
        is_featured=True,
    )
    pack = _create_pack(
        section,
        name="Pack Premium",
        price=15000,
        promotional_price=12000,
        is_featured=True,
    )
    PackArea.objects.create(pack=pack, area=area)

    settings = WaxingSettings.objects.order_by("-created_at").first()
    settings.show_prices = False
    settings.save(update_fields=["show_prices"])

    response = client.get("/api/v1/waxing/?section=mujer")
    assert response.status_code == 200

    category_items = response.data["sections_by_gender"]["mujer"]["categories"][0]["items"]
    items_by_name = {item["name"]: item for item in category_items}
    assert items_by_name["Axilas"]["price"] is None
    assert items_by_name["Axilas"]["price_without_discount"] is None
    assert items_by_name["Pack Premium"]["price"] is None
    assert items_by_name["Pack Premium"]["price_without_discount"] is None

    featured_items = response.data["featured_by_gender"]["mujer"]
    featured_by_name = {item["name"]: item for item in featured_items}
    assert featured_by_name["Axilas"]["price"] is None
    assert featured_by_name["Axilas"]["price_without_discount"] is None
    assert featured_by_name["Pack Premium"]["price"] is None
    assert featured_by_name["Pack Premium"]["price_without_discount"] is None


@pytest.mark.django_db
def test_public_summary_endpoint_contract():
    client = APIClient()
    settings = WaxingSettings.objects.order_by("-created_at").first()
    content = WaxingContent.objects.order_by("-created_at").first()

    settings.is_enabled = False
    settings.public_visible = False
    settings.maintenance_mode = True
    settings.maintenance_message = "Estamos actualizando el servicio."
    settings.save(
        update_fields=[
            "is_enabled",
            "public_visible",
            "maintenance_mode",
            "maintenance_message",
        ]
    )

    content.title = "Landing Waxing"
    content.short_description = "Resumen corto de waxing."
    content.description = "Descripcion completa de waxing."
    content.save(update_fields=["title", "short_description", "description"])

    response = client.get("/api/v1/waxing/summary/")
    assert response.status_code == 200
    assert set(response.data.keys()) == {
        "title",
        "short_description",
        "image",
        "is_enabled",
        "public_visible",
        "maintenance_mode",
        "maintenance_message",
    }
    assert response.data["title"] == "Landing Waxing"
    assert response.data["short_description"] == "Resumen corto de waxing."
    assert response.data["is_enabled"] is False
    assert response.data["public_visible"] is False
    assert response.data["maintenance_mode"] is True
    assert response.data["maintenance_message"] == "Estamos actualizando el servicio."


@pytest.mark.django_db
def test_admin_summary_endpoint_requires_staff_and_returns_full_dataset_without_pagination():
    client = APIClient()
    unauthorized_response = client.get("/api/v1/waxing/waxing/")
    assert unauthorized_response.status_code in {401, 403}

    staff = _staff_user()
    client.force_authenticate(staff)

    section = _create_section("mujer", is_active=False)
    category = _create_category(section, name="Piernas", is_active=False)
    area = _create_area(section, category, name="Axilas", is_active=False)
    pack = _create_pack(section, name="Pack Premium", is_active=False, is_featured=True)
    PackArea.objects.create(pack=pack, area=area, order=0)
    FeaturedItemOrder.objects.create(
        section=section,
        item_kind=FeaturedItemOrder.ItemKind.PACK,
        item_id=pack.id,
        order=0,
    )

    content = WaxingContent.objects.order_by("-created_at").first()
    content.title = "Contenido admin"
    content.save(update_fields=["title"])
    benefit = content.benefits.create(
        title="Beneficio admin",
        detail="Detalle",
        order=0,
        is_active=False,
    )
    recommendation = content.recommendations.create(
        title="Recomendacion admin",
        detail="Detalle",
        order=0,
        is_active=False,
    )
    faq = content.faqs.create(
        question="Pregunta admin",
        answer="Respuesta admin",
        order=0,
        is_active=False,
    )

    response = client.get("/api/v1/waxing/waxing/")
    assert response.status_code == 200
    assert set(response.data.keys()) == {
        "settings",
        "sections",
        "area_categories",
        "areas",
        "packs",
        "pack_areas",
        "featured_orders",
        "content",
        "benefits",
        "recommendations",
        "faqs",
    }
    assert "results" not in response.data
    assert any(item["id"] == str(section.id) for item in response.data["sections"])
    assert any(item["id"] == str(category.id) for item in response.data["area_categories"])
    assert any(item["id"] == str(area.id) for item in response.data["areas"])
    assert any(item["id"] == str(pack.id) for item in response.data["packs"])
    assert any(item["id"] == str(benefit.id) for item in response.data["benefits"])
    assert any(
        item["id"] == str(recommendation.id)
        for item in response.data["recommendations"]
    )
    assert any(item["id"] == str(faq.id) for item in response.data["faqs"])
    content_rows = {item["id"]: item for item in response.data["content"]}
    assert content_rows[str(content.id)]["title"] == "Contenido admin"
    assert any(item["id"] == str(benefit.id) for item in content_rows[str(content.id)]["benefits"])


@pytest.mark.django_db
def test_public_rejects_gender_query_param():
    client = APIClient()
    _create_section("mujer")

    response = client.get("/api/v1/waxing/?gender=mujer")
    assert response.status_code == 400
    assert "section" in response.data


@pytest.mark.django_db
def test_promotional_price_validation_for_area_and_pack():
    staff = _staff_user()
    client = APIClient()
    client.force_authenticate(staff)

    section = _create_section("mujer")
    category = _create_category(section)

    area_resp = client.post(
        "/api/v1/waxing/areas/",
        {
            "section": str(section.id),
            "category": str(category.id),
            "name": "Area invalida",
            "price": 1000,
            "promotional_price": 1000,
            "order": 0,
            "is_active": True,
        },
        format="json",
    )
    assert area_resp.status_code == 400
    assert "promotional_price" in area_resp.data

    pack_resp = client.post(
        "/api/v1/waxing/packs/",
        {
            "section": str(section.id),
            "name": "Pack invalido",
            "price": 2000,
            "promotional_price": 2000,
            "order": 0,
            "is_active": True,
        },
        format="json",
    )
    assert pack_resp.status_code == 400
    assert "promotional_price" in pack_resp.data


@pytest.mark.django_db
def test_duration_validation_for_area_and_pack():
    staff = _staff_user()
    client = APIClient()
    client.force_authenticate(staff)

    section = _create_section("mujer")
    category = _create_category(section)

    area_resp = client.post(
        "/api/v1/waxing/areas/",
        {
            "section": str(section.id),
            "category": str(category.id),
            "name": "Area invalida duration",
            "price": 1000,
            "duration": 0,
            "order": 0,
            "is_active": True,
        },
        format="json",
    )
    assert area_resp.status_code == 400
    assert "duration" in area_resp.data

    pack_resp = client.post(
        "/api/v1/waxing/packs/",
        {
            "section": str(section.id),
            "name": "Pack invalido duration",
            "price": 2000,
            "duration": 0,
            "order": 0,
            "is_active": True,
        },
        format="json",
    )
    assert pack_resp.status_code == 400
    assert "duration" in pack_resp.data


@pytest.mark.django_db
def test_pack_area_rejects_mismatched_section():
    staff = _staff_user()
    client = APIClient()
    client.force_authenticate(staff)

    mujer = _create_section("mujer")
    hombre = _create_section("hombre")
    category_hombre = _create_category(hombre)
    area_hombre = _create_area(hombre, category_hombre)
    pack_mujer = _create_pack(mujer)

    response = client.post(
        "/api/v1/waxing/pack_areas/",
        {
            "pack": str(pack_mujer.id),
            "area": str(area_hombre.id),
            "order": 0,
        },
        format="json",
    )
    assert response.status_code == 400
    assert "area" in response.data


@pytest.mark.django_db
def test_multi_category_pack_requires_featured():
    staff = _staff_user()
    client = APIClient()
    client.force_authenticate(staff)

    section = _create_section("mujer")
    cat_a = _create_category(section, name="Cat A")
    cat_b = _create_category(section, name="Cat B")
    area_a = _create_area(section, cat_a, name="Area A")
    area_b = _create_area(section, cat_b, name="Area B")
    pack = _create_pack(section, name="Pack multi", is_featured=False)

    first = client.post(
        "/api/v1/waxing/pack_areas/",
        {"pack": str(pack.id), "area": str(area_a.id), "order": 0},
        format="json",
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/waxing/pack_areas/",
        {"pack": str(pack.id), "area": str(area_b.id), "order": 1},
        format="json",
    )
    assert second.status_code == 400
    assert "pack" in second.data


@pytest.mark.django_db
def test_multi_category_pack_not_shown_inside_categories():
    client = APIClient()
    section = _create_section("mujer", featured_sort=SortOption.MANUAL)
    cat_1 = _create_category(section, name="Cat1", show_packs=True)
    cat_2 = _create_category(section, name="Cat2", show_packs=True)
    area_1 = _create_area(section, cat_1, name="Area Cat1")
    area_2 = _create_area(section, cat_2, name="Area Cat2")
    pack = _create_pack(section, name="Pack Multi Cat", is_featured=True)
    PackArea.objects.create(pack=pack, area=area_1, order=0)
    PackArea.objects.create(pack=pack, area=area_2, order=1)

    response = client.get("/api/v1/waxing/?section=mujer")
    categories = response.data["sections_by_gender"]["mujer"]["categories"]
    items_cat_1 = categories[0]["items"]
    items_cat_2 = categories[1]["items"]
    assert all(item["name"] != "Pack Multi Cat" for item in items_cat_1)
    assert all(item["name"] != "Pack Multi Cat" for item in items_cat_2)


@pytest.mark.django_db
def test_featured_mixed_manual_and_non_manual_ordering():
    client = APIClient()
    section = _create_section("mujer", featured_sort=SortOption.MANUAL)
    category = _create_category(section)
    area_z = _create_area(section, category, name="Zona Z", price=5000, is_featured=True)
    area_b = _create_area(section, category, name="Zona B", price=3000, is_featured=True)
    pack_a = _create_pack(section, name="Pack A", price=10000, is_featured=True)
    PackArea.objects.create(pack=pack_a, area=area_z, order=0)
    FeaturedItemOrder.objects.create(
        section=section,
        item_kind=FeaturedItemOrder.ItemKind.PACK,
        item_id=pack_a.id,
        order=0,
    )

    manual_response = client.get("/api/v1/waxing/?section=mujer")
    manual_items = manual_response.data["featured_by_gender"]["mujer"]
    assert manual_items[0]["kind"] == "pack"
    assert [item["name"] for item in manual_items[1:]] == ["Zona B", "Zona Z"]

    section.featured_sort = SortOption.PRICE_DESC
    section.save(update_fields=["featured_sort"])

    non_manual_response = client.get("/api/v1/waxing/?section=mujer")
    non_manual_names = [item["name"] for item in non_manual_response.data["featured_by_gender"]["mujer"]]
    assert non_manual_names == ["Pack A", "Zona Z", "Zona B"]


@pytest.mark.django_db
def test_price_sort_uses_effective_price_when_promotions_exist():
    client = APIClient()
    section = _create_section("mujer", featured_sort=SortOption.PRICE_ASC)
    category = _create_category(
        section,
        name="Rostro",
        area_sort=SortOption.PRICE_ASC,
        show_packs=False,
    )
    _create_area(
        section,
        category,
        name="Area base 1000",
        price=1000,
        is_featured=True,
    )
    _create_area(
        section,
        category,
        name="Area promo 900",
        price=1500,
        promotional_price=900,
        is_featured=True,
    )

    response = client.get("/api/v1/waxing/?section=mujer")
    assert response.status_code == 200

    category_items = response.data["sections_by_gender"]["mujer"]["categories"][0]["items"]
    assert [item["name"] for item in category_items] == ["Area promo 900", "Area base 1000"]
    assert [item["price"] for item in category_items] == [900, 1000]

    featured_items = response.data["featured_by_gender"]["mujer"]
    assert [item["name"] for item in featured_items] == ["Area promo 900", "Area base 1000"]
    assert [item["price"] for item in featured_items] == [900, 1000]


@pytest.mark.django_db
def test_category_area_pack_ordering_and_mix_respects_pack_position():
    client = APIClient()
    section = _create_section("mujer")
    category_first = _create_category(
        section,
        name="B Category",
        order=2,
        area_sort=SortOption.MANUAL,
        pack_sort=SortOption.PRICE_DESC,
        pack_position="first",
    )
    category_second = _create_category(
        section,
        name="A Category",
        order=1,
        show_packs=False,
    )

    area_2 = _create_area(section, category_first, name="Area 2", order=2, price=500)
    area_1 = _create_area(section, category_first, name="Area 1", order=1, price=900)
    pack_low = _create_pack(section, name="Pack low", price=1000)
    pack_high = _create_pack(section, name="Pack high", price=2000)
    PackArea.objects.create(pack=pack_low, area=area_1, order=0)
    PackArea.objects.create(pack=pack_high, area=area_2, order=0)

    response = client.get("/api/v1/waxing/?section=mujer")
    categories = response.data["sections_by_gender"]["mujer"]["categories"]
    assert [cat["name"] for cat in categories] == ["A Category", "B Category"]

    first_category_items = categories[1]["items"]
    assert [(item["kind"], item["name"]) for item in first_category_items] == [
        ("pack", "Pack high"),
        ("pack", "Pack low"),
        ("area", "Area 1"),
        ("area", "Area 2"),
    ]


@pytest.mark.django_db
def test_show_packs_false_hides_single_category_packs():
    client = APIClient()
    section = _create_section("mujer")
    category = _create_category(section, show_packs=False)
    area = _create_area(section, category, name="Area 1")
    pack = _create_pack(section, name="Pack 1")
    PackArea.objects.create(pack=pack, area=area, order=0)

    response = client.get("/api/v1/waxing/?section=mujer")
    items = response.data["sections_by_gender"]["mujer"]["categories"][0]["items"]
    assert len(items) == 1
    assert items[0]["kind"] == "area"


@pytest.mark.django_db
def test_permissions_public_read_and_staff_write():
    client = APIClient()
    read_resp = client.get("/api/v1/waxing/sections/")
    assert read_resp.status_code == 200

    write_resp = client.post(
        "/api/v1/waxing/sections/",
        {"name": "mujer"},
        format="json",
    )
    assert write_resp.status_code in {401, 403}

    staff = _staff_user()
    client.force_authenticate(staff)
    staff_write_resp = client.post(
        "/api/v1/waxing/sections/",
        {"name": "mujer"},
        format="json",
    )
    assert staff_write_resp.status_code == 201


@pytest.mark.django_db
def test_waxing_settings_enabled_disabled_behavior():
    client = APIClient()
    settings = WaxingSettings.objects.order_by("-created_at").first()
    settings.is_enabled = False
    settings.save(update_fields=["is_enabled"])

    response = client.get("/api/v1/waxing/")
    assert response.status_code == 503
    assert response.data["status"] == "disabled"
    assert response.data["is_enabled"] is False


@pytest.mark.django_db
def test_public_endpoint_supports_more_than_two_sections():
    client = APIClient()
    _create_section("mujer")
    _create_section("hombre")
    _create_section("adolescente")

    response = client.get("/api/v1/waxing/")
    assert response.status_code == 200
    assert set(response.data["genders"]) == {"mujer", "hombre", "adolescente"}
    assert set(response.data["sections_by_gender"].keys()) == {
        "mujer",
        "hombre",
        "adolescente",
    }


@pytest.mark.django_db
def test_sections_are_ordered_by_creation_date_in_public_and_crud():
    client = APIClient()
    newest = _create_section("zeta")
    oldest = _create_section("alfa")

    now = timezone.now()
    Section.objects.filter(pk=oldest.pk).update(created_at=now - timedelta(hours=2))
    Section.objects.filter(pk=newest.pk).update(created_at=now - timedelta(hours=1))

    public_response = client.get("/api/v1/waxing/")
    assert public_response.status_code == 200
    assert public_response.data["genders"] == ["zeta", "alfa"]

    crud_response = client.get("/api/v1/waxing/sections/")
    assert crud_response.status_code == 200
    assert [item["name"] for item in crud_response.data["results"]] == ["zeta", "alfa"]


@pytest.mark.django_db
def test_area_order_autoincrements_within_category_when_omitted():
    section = _create_section("mujer")
    category = _create_category(section)
    first = _create_area(section, category, name="A0")
    second = _create_area(section, category, name="A1")
    third = Area.objects.create(
        section=section,
        category=category,
        name="A2",
        price=1500,
    )

    assert first.order == 0
    assert second.order == 0
    assert third.order == 0


@pytest.mark.django_db
def test_area_order_reassigned_when_category_changes():
    section = _create_section("mujer")
    category_a = _create_category(section, name="Cat A")
    category_b = _create_category(section, name="Cat B")
    area_a = _create_area(section, category_a, name="A0")
    _create_area(section, category_b, name="B0")

    assert area_a.order == 0
    area_a.category = category_b
    area_a.save()
    area_a.refresh_from_db()

    assert area_a.order == 0


@pytest.mark.django_db
def test_area_order_not_changed_when_category_stays_the_same():
    section = _create_section("mujer")
    category_a = _create_category(section, name="Cat A")
    area = _create_area(section, category_a, name="A0")
    original_order = area.order

    area.name = "A0 editado"
    area.save()
    area.refresh_from_db()

    assert area.order == original_order


@pytest.mark.django_db
def test_manual_sort_breaks_order_ties_with_newest_first():
    client = APIClient()
    section = _create_section("mujer")
    category = _create_category(
        section,
        area_sort=SortOption.MANUAL,
        pack_sort=SortOption.MANUAL,
        pack_position="first",
    )

    old_area = _create_area(section, category, name="Area vieja")
    new_area = _create_area(section, category, name="Area nueva")
    old_pack = _create_pack(section, name="Pack viejo")
    new_pack = _create_pack(section, name="Pack nuevo")
    PackArea.objects.create(pack=old_pack, area=old_area, order=0)
    PackArea.objects.create(pack=new_pack, area=old_area, order=0)

    now = timezone.now()
    Area.objects.filter(pk=old_area.pk).update(created_at=now - timedelta(hours=2))
    Area.objects.filter(pk=new_area.pk).update(created_at=now - timedelta(hours=1))
    Pack.objects.filter(pk=old_pack.pk).update(created_at=now - timedelta(hours=2))
    Pack.objects.filter(pk=new_pack.pk).update(created_at=now - timedelta(hours=1))

    response = client.get("/api/v1/waxing/?section=mujer")
    items = response.data["sections_by_gender"]["mujer"]["categories"][0]["items"]
    assert [item["name"] for item in items] == [
        "Pack nuevo",
        "Pack viejo",
        "Area nueva",
        "Area vieja",
    ]


@pytest.mark.django_db
def test_pack_order_autoincrements_within_category_when_single_category():
    section = _create_section("mujer")
    category = _create_category(section)
    area_a = _create_area(section, category, name="AZ")
    area_b = _create_area(section, category, name="AX")
    area_c = _create_area(section, category, name="AY")

    first = _create_pack(section, name="P0")
    PackArea.objects.create(pack=first, area=area_a, order=0)
    second = _create_pack(section, name="P1")
    PackArea.objects.create(pack=second, area=area_b, order=0)
    third = Pack.objects.create(
        section=section,
        name="P2",
        price=9000,
    )
    PackArea.objects.create(pack=third, area=area_c, order=0)

    assert first.order == 0
    assert second.order == 0
    assert third.order == 0


@pytest.mark.django_db
def test_pack_order_not_changed_when_unique_category_stays_the_same():
    section = _create_section("mujer")
    category = _create_category(section, name="Cat A")
    area_a = _create_area(section, category, name="A1")
    area_b = _create_area(section, category, name="A2")
    pack = _create_pack(section, name="Pack A")
    PackArea.objects.create(pack=pack, area=area_a, order=0)
    original_order = pack.order

    PackArea.objects.create(pack=pack, area=area_b, order=1)
    pack.refresh_from_db()

    assert pack.order == original_order


@pytest.mark.django_db
def test_pack_order_reassigned_when_unique_category_changes():
    section = _create_section("mujer")
    category_a = _create_category(section, name="Cat A")
    category_b = _create_category(section, name="Cat B")
    area_a = _create_area(section, category_a, name="A1")
    area_b1 = _create_area(section, category_b, name="B1")
    area_b2 = _create_area(section, category_b, name="B2")

    pack_b_existing = _create_pack(section, name="Pack B Existing")
    PackArea.objects.create(pack=pack_b_existing, area=area_b1, order=0)

    pack = _create_pack(section, name="Pack To Move")
    link = PackArea.objects.create(pack=pack, area=area_a, order=0)
    assert pack.order == 0

    link.area = area_b2
    link.save()
    pack.refresh_from_db()

    assert pack.order == 0


@pytest.mark.django_db
def test_pack_order_reassigned_when_transition_from_multi_to_unique():
    section = _create_section("mujer")
    category_a = _create_category(section, name="Cat A")
    category_b = _create_category(section, name="Cat B")
    area_a = _create_area(section, category_a, name="A1")
    area_b = _create_area(section, category_b, name="B1")
    area_b2 = _create_area(section, category_b, name="B2")

    pack_b_existing = _create_pack(section, name="Pack B Existing")
    PackArea.objects.create(pack=pack_b_existing, area=area_b2, order=0)

    pack = _create_pack(section, name="Pack Multi", is_featured=True)
    link_a = PackArea.objects.create(pack=pack, area=area_a, order=0)
    PackArea.objects.create(pack=pack, area=area_b, order=1)
    Pack.objects.filter(pk=pack.pk).update(order=99)
    pack.refresh_from_db()
    assert pack.order == 99

    link_a.delete()
    pack.refresh_from_db()

    assert pack.order == 0


@pytest.mark.django_db
def test_pack_order_not_changed_when_unique_goes_to_multi_or_none():
    section = _create_section("mujer")
    category_a = _create_category(section, name="Cat A")
    category_b = _create_category(section, name="Cat B")
    area_a = _create_area(section, category_a, name="A1")
    area_b = _create_area(section, category_b, name="B1")

    pack = _create_pack(section, name="Pack Stable", is_featured=True)
    link_a = PackArea.objects.create(pack=pack, area=area_a, order=0)
    base_order = pack.order

    PackArea.objects.create(pack=pack, area=area_b, order=1)
    pack.refresh_from_db()
    assert pack.order == base_order

    link_a.delete()
    for link in list(pack.pack_areas.all()):
        link.delete()
    pack.refresh_from_db()
    assert pack.order == base_order


@pytest.mark.django_db
def test_pack_position_default_is_first():
    section = _create_section("mujer")
    category = _create_category(section)
    settings = WaxingSettings.objects.order_by("-created_at").first()

    assert category.pack_position == "first"
    assert settings.default_pack_position == "first"


@pytest.mark.django_db
def test_reorder_category_areas_endpoint_updates_sequential_order():
    staff = _staff_user()
    client = APIClient()
    client.force_authenticate(staff)

    section = _create_section("mujer")
    category = _create_category(section)
    area_1 = _create_area(section, category, name="A1")
    area_2 = _create_area(section, category, name="A2")
    area_3 = _create_area(section, category, name="A3")

    response = client.post(
        f"/api/v1/waxing/categories/{category.id}/areas/reorder/",
        {"items": [str(area_3.id), str(area_1.id), str(area_2.id)]},
        format="json",
    )
    assert response.status_code == 200
    area_1.refresh_from_db()
    area_2.refresh_from_db()
    area_3.refresh_from_db()
    assert (area_3.order, area_1.order, area_2.order) == (0, 1, 2)


@pytest.mark.django_db
def test_reorder_category_packs_endpoint_rejects_partial_list():
    staff = _staff_user()
    client = APIClient()
    client.force_authenticate(staff)

    section = _create_section("mujer")
    category = _create_category(section)
    area_1 = _create_area(section, category, name="A1")
    area_2 = _create_area(section, category, name="A2")
    pack_1 = _create_pack(section, name="P1")
    pack_2 = _create_pack(section, name="P2")
    PackArea.objects.create(pack=pack_1, area=area_1, order=0)
    PackArea.objects.create(pack=pack_2, area=area_2, order=0)

    response = client.post(
        f"/api/v1/waxing/categories/{category.id}/packs/reorder/",
        {"items": [str(pack_1.id)]},
        format="json",
    )
    assert response.status_code == 400
    assert "items" in response.data


@pytest.mark.django_db
def test_reorder_section_featured_endpoint_updates_mixed_order():
    staff = _staff_user()
    client = APIClient()
    client.force_authenticate(staff)

    section = _create_section("mujer")
    category = _create_category(section)
    area = _create_area(section, category, name="Area X", is_featured=True)
    pack = _create_pack(section, name="Pack X", is_featured=True)
    PackArea.objects.create(pack=pack, area=area, order=0)

    response = client.post(
        f"/api/v1/waxing/sections/{section.id}/featured/reorder/",
        {
            "items": [
                {"item_kind": "pack", "item_id": str(pack.id)},
                {"item_kind": "area", "item_id": str(area.id)},
            ]
        },
        format="json",
    )
    assert response.status_code == 200
    rows = list(FeaturedItemOrder.objects.filter(section=section).order_by("order"))
    assert [(row.item_kind, row.item_id) for row in rows] == [
        ("pack", pack.id),
        ("area", area.id),
    ]


@pytest.mark.django_db
def test_singleton_endpoints_reject_creating_second_row():
    staff = _staff_user()
    client = APIClient()
    client.force_authenticate(staff)

    settings_count_before = WaxingSettings.objects.count()
    content_count_before = WaxingContent.objects.count()

    settings_resp = client.post(
        "/api/v1/waxing/settings/",
        {"is_enabled": True},
        format="json",
    )
    content_resp = client.post(
        "/api/v1/waxing/content/",
        {
            "title": "Nuevo",
            "description": "Nuevo contenido",
        },
        format="json",
    )

    assert settings_resp.status_code == 400
    assert content_resp.status_code == 400
    assert WaxingSettings.objects.count() == settings_count_before
    assert WaxingContent.objects.count() == content_count_before


@pytest.mark.django_db
def test_content_patch_supports_nested_benefits_recommendations_and_faqs():
    staff = _staff_user()
    client = APIClient()
    client.force_authenticate(staff)

    content = WaxingContent.objects.order_by("-created_at").first()
    benefit_keep = content.benefits.create(
        title="B mantener",
        detail="x",
        order=0,
        is_active=True,
    )
    benefit_remove = content.benefits.create(
        title="B borrar",
        detail="x",
        order=1,
        is_active=True,
    )
    recommendation_keep = content.recommendations.create(
        title="R mantener",
        detail="x",
        order=0,
        is_active=True,
    )
    faq_keep = content.faqs.create(
        question="Q mantener",
        answer="A mantener",
        order=0,
        is_active=True,
    )

    response = client.patch(
        f"/api/v1/waxing/content/{content.id}/",
        {
            "title": "Contenido waxing",
            "description": "Descripcion principal",
            "benefits": [
                {
                    "id": str(benefit_keep.id),
                    "title": "B actualizado",
                    "detail": "detalle actualizado",
                    "order": 0,
                    "is_active": False,
                },
                {
                    "title": "B nuevo",
                    "detail": "detalle nuevo",
                    "is_active": True,
                },
            ],
            "benefits_remove_ids": [str(benefit_remove.id)],
            "recommendations": [
                {
                    "id": str(recommendation_keep.id),
                    "title": "R actualizado",
                    "detail": "detalle r actualizado",
                },
                {
                    "title": "R nuevo",
                    "detail": "detalle r nuevo",
                },
            ],
            "faqs": [
                {
                    "id": str(faq_keep.id),
                    "question": "Q actualizada",
                    "answer": "A actualizada",
                },
                {
                    "question": "Q nueva",
                    "answer": "A nueva",
                },
            ],
        },
        format="json",
    )
    assert response.status_code == 200

    content.refresh_from_db()

    benefits = list(content.benefits.order_by("order", "id"))
    assert [item.title for item in benefits] == ["B actualizado", "B nuevo"]
    assert [item.order for item in benefits] == [0, 1]
    assert benefits[0].is_active is False

    recommendations = list(content.recommendations.order_by("order", "id"))
    assert [item.title for item in recommendations] == ["R actualizado", "R nuevo"]
    assert [item.order for item in recommendations] == [0, 1]

    faqs = list(content.faqs.order_by("order", "id"))
    assert [item.question for item in faqs] == ["Q actualizada", "Q nueva"]
    assert [item.order for item in faqs] == [0, 1]
