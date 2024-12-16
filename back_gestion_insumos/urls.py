"""
URL configuration for gestion_insumos_back project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from userApp.views import UsuarioCreateView, CustomTokenObtainPairView
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    # Administración
    path('admin/', admin.site.urls),

    # Usuarios
    path('usuario/', include('userApp.routes')),  # Rutas del módulo de usuario
    path('api/user/register/', UsuarioCreateView.as_view(), name="register"),
    path('api/token/', CustomTokenObtainPairView.as_view(), name="get_token"),
    path('api/token/refresh/', TokenRefreshView.as_view(), name="refresh"),
    path('api-auth/', include('rest_framework.urls')),  # Rutas para autenticación de la API

    # Subjects (Asignaturas, Clases, Solicitudes y Notificaciones)
    path('subjects/', include('subjectsApp.routes')),  # Rutas del módulo de asignaturas, solicitudes y notificaciones

    # Insumos
    path('insumos/', include('insumosApp.routes')),  # Rutas del módulo de insumos
]


