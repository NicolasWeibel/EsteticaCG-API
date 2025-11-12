from ..models import Category
from .base import UUIDSerializer


class CategorySerializer(UUIDSerializer):
    class Meta:
        model = Category
        fields = "__all__"
