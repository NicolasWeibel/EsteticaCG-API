from django.contrib import admin
from ..models import TreatmentType, Objective, IntensityLevel, DurationBucket


@admin.register(TreatmentType)
class TreatmentTypeAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Objective)
class ObjectiveAdmin(admin.ModelAdmin):
    list_display = ("name", "image")
    search_fields = ("name",)


@admin.register(IntensityLevel)
class IntensityLevelAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(DurationBucket)
class DurationBucketAdmin(admin.ModelAdmin):
    list_display = ("name", "minutes")
    search_fields = ("name",)
