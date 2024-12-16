from rest_framework.routers import DefaultRouter
from .views import UsuarioView, UsuarioPorRolView
from django.urls import path

router = DefaultRouter()
router.register('usuario', UsuarioView, basename='usuario')
urlpatterns = router.urls

# Añadir la nueva vista para filtrar usuarios por rol
urlpatterns += [
    path('usuarios_por_rol/', UsuarioPorRolView.as_view(), name='usuarios_por_rol'),
]

