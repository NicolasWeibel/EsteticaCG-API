from django.contrib import admin

from .models import GoogleReviewCache, ManualReview


@admin.register(ManualReview)
class ManualReviewAdmin(admin.ModelAdmin):
    list_display = ("author_name", "rating", "is_active", "order", "created_at")
    list_editable = ("is_active", "order")
    list_filter = ("is_active", "rating")
    search_fields = ("author_name", "comment")


@admin.register(GoogleReviewCache)
class GoogleReviewCacheAdmin(admin.ModelAdmin):
    list_display = (
        "external_id",
        "reviewer_name",
        "rating",
        "is_hidden",
        "fetched_at",
        "update_time",
    )
    list_editable = ("is_hidden",)
    list_filter = ("is_hidden", "rating", "reviewer_is_anonymous")
    search_fields = ("external_id", "reviewer_name", "comment", "hidden_reason")
    readonly_fields = (
        "external_id",
        "reviewer_name",
        "reviewer_profile_photo_url",
        "reviewer_is_anonymous",
        "rating",
        "comment",
        "create_time",
        "update_time",
        "fetched_at",
        "raw_payload",
        "created_at",
        "updated_at",
    )
