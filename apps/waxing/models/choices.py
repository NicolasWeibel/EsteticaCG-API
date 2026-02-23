from django.db import models


class SortOption(models.TextChoices):
    PRICE_ASC = "price_asc", "Price asc"
    PRICE_DESC = "price_desc", "Price desc"
    AZ = "az", "A-Z"
    ZA = "za", "Z-A"
    MANUAL = "manual", "Manual"


class PackPosition(models.TextChoices):
    FIRST = "first", "First"
    LAST = "last", "Last"
