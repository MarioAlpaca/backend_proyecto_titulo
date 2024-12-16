from django.urls import path
from . import views

urlpatterns = [
    path("insumos_c/", views.InsumoCrear.as_view(), name="crear-insumo"),
    path("insumos_e/delete/<int:pk>", views.InsumoEliminar.as_view(), name="eliminar-insumo")
]