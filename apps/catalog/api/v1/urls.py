from rest_framework.routers import DefaultRouter
from .views import TreatmentViewSet

router = DefaultRouter()
router.register("treatments", TreatmentViewSet, basename="treatments")
urlpatterns = router.urls
