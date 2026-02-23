from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import AreaCategory, WaxingContent, WaxingSettings
from ..models.section import Section
from ..serializers import WaxingPublicQuerySerializer
from ..services import (
    image_url,
    serialize_area,
    serialize_category,
    serialize_pack,
    single_category_packs_for_category,
    sort_featured_items,
    sort_items,
)


class WaxingPublicView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        if "gender" in request.query_params:
            raise ValidationError(
                {"section": "Usa el parametro 'section' en lugar de 'gender'."}
            )
        query = WaxingPublicQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        selected_section = query.validated_data.get("section")

        settings_obj = WaxingSettings.objects.order_by("-created_at").first()
        if settings_obj and not settings_obj.is_enabled:
            return Response(
                {
                    "category": "waxing",
                    "status": "disabled",
                    "is_enabled": False,
                    "message": "Waxing no se encuentra habilitado actualmente.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        sections = list(Section.objects.filter(is_active=True).order_by("name"))
        section_names = [section.name for section in sections]

        payload = {
            "category": "waxing",
            "genders": section_names,
            "sections_by_gender": {},
            "featured_by_gender": {},
            "content": self._serialize_content(),
        }

        show_prices = True if settings_obj is None else settings_obj.show_prices
        featured_enabled = True if settings_obj is None else settings_obj.featured_enabled
        public_visible = True if settings_obj is None else settings_obj.public_visible

        for section in sections:
            section_name = section.name
            if (selected_section and selected_section != section_name) or not public_visible:
                payload["sections_by_gender"][section_name] = {}
                payload["featured_by_gender"][section_name] = []
                continue

            categories_payload = []
            categories = AreaCategory.objects.filter(
                section=section,
                is_active=True,
            ).order_by("order", "name")

            for category in categories:
                areas = sort_items(
                    category.areas.filter(is_active=True),
                    category.area_sort,
                )
                packs = []
                if category.show_packs:
                    packs = sort_items(
                        single_category_packs_for_category(category),
                        category.pack_sort,
                    )
                categories_payload.append(
                    serialize_category(
                        category,
                        areas=areas,
                        packs=packs,
                        show_prices=show_prices,
                    )
                )

            payload["sections_by_gender"][section_name] = {
                "section": {
                    "id": section.id,
                    "name": section.name,
                    "image": image_url(section.image),
                    "featured_sort": section.featured_sort,
                },
                "categories": categories_payload,
            }

            featured_items = []
            if featured_enabled:
                for kind, item in sort_featured_items(section, section.featured_sort):
                    if kind == "area":
                        featured_items.append(serialize_area(item, show_prices=show_prices))
                    else:
                        featured_items.append(serialize_pack(item, show_prices=show_prices))
            payload["featured_by_gender"][section_name] = featured_items

        if selected_section and selected_section not in payload["sections_by_gender"]:
            payload["sections_by_gender"][selected_section] = {}
            payload["featured_by_gender"][selected_section] = []

        return Response(payload, status=status.HTTP_200_OK)

    def _serialize_content(self):
        content = (
            WaxingContent.objects.prefetch_related(
                "benefits",
                "recommendations",
                "faqs",
            )
            .order_by("-created_at")
            .first()
        )
        if content is None:
            return {
                "title": "",
                "short_description": "",
                "description": "",
                "recommendations_intro_text": "",
                "image": None,
                "benefits_image": None,
                "recommendations_image": None,
                "benefits": [],
                "recommendations": [],
                "faqs": [],
            }

        return {
            "id": content.id,
            "title": content.title,
            "short_description": content.short_description,
            "description": content.description,
            "recommendations_intro_text": content.recommendations_intro_text,
            "image": image_url(content.image),
            "benefits_image": image_url(content.benefits_image),
            "recommendations_image": image_url(content.recommendations_image),
            "benefits": [
                {
                    "id": item.id,
                    "title": item.title,
                    "detail": item.detail,
                    "order": item.order,
                }
                for item in content.benefits.filter(is_active=True).order_by("order")
            ],
            "recommendations": [
                {
                    "id": item.id,
                    "title": item.title,
                    "detail": item.detail,
                    "order": item.order,
                }
                for item in content.recommendations.filter(is_active=True).order_by("order")
            ],
            "faqs": [
                {
                    "id": item.id,
                    "question": item.question,
                    "answer": item.answer,
                    "order": item.order,
                }
                for item in content.faqs.filter(is_active=True).order_by("order")
            ],
        }
