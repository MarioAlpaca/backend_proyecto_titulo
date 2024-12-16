from rest_framework.routers import DefaultRouter
from .views import InsumoView

router = DefaultRouter()
router.register(r'insumos', InsumoView, basename='insumo')
# router.register(r'clase_insumos', ClaseInsumoView, basename='clase_insumo')
# router.register(r'solicitud_insumos', SolicitudInsumoView, basename='solicitud_insumo')

urlpatterns = router.urls
