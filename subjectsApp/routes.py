# routes.py en subjectsApp

from rest_framework.routers import DefaultRouter
from .views import AsignaturaView, ClaseViewSet, SolicitudInsumoViewSet, NotificacionViewSet

router = DefaultRouter()
router.register('asignaturas', AsignaturaView, basename='asignatura')  # Registrar rutas para asignaturas
router.register('clases', ClaseViewSet, basename='clase')  # Registrar rutas para clases
router.register('solicitudes', SolicitudInsumoViewSet, basename='solicitudes')  # Registrar rutas para solicitudes
router.register('notificaciones', NotificacionViewSet, basename='notificaciones')  # Registrar rutas para notificaciones

urlpatterns = router.urls

