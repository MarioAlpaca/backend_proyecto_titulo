from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import viewsets, generics
from .models import Insumo
from .serializers import InsumoSerializer
from rest_framework import status
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from .models import Insumo
from subjectsApp.models import ClaseInsumo, Clase
from django.db.models import Q

# CRUD para Insumo con paginación
class InsumoView(viewsets.ModelViewSet):
    queryset = Insumo.objects.all().order_by('nombre')  # Ordenar por el campo 'nombre'
    serializer_class = InsumoSerializer
    permission_classes = [IsAuthenticated]  # Solo usuarios autenticados pueden acceder

    def perform_update(self, serializer):
        """Actualizar la cantidad de un insumo si está asignado a una clase iniciada."""
        insumo = self.get_object()
        clases_iniciadas = ClaseInsumo.objects.filter(
            insumo=insumo,
            clase__estado="iniciada"
        )

        # Verificar si se está intentando cambiar el nombre de un insumo asignado a una clase iniciada
        if clases_iniciadas.exists() and 'nombre' in serializer.validated_data and serializer.validated_data['nombre'] != insumo.nombre:
            raise ValidationError("No se puede modificar el nombre de un insumo que está asignado a una clase iniciada.")
        
        # Permitir la actualización de la cantidad total
        serializer.save()


    def perform_destroy(self, instance):
        """Eliminar un insumo si no está asignado a una clase iniciada."""
        clases_iniciadas = ClaseInsumo.objects.filter(
            insumo=instance,
            clase__estado="iniciada"
        )

        if clases_iniciadas.exists():
            raise ValidationError("No se puede eliminar un insumo que está asignado a una clase iniciada.")

        instance.delete()


# Crear un nuevo insumo (si necesitas una vista separada para esto)
class InsumoCrear(generics.CreateAPIView):
    serializer_class = InsumoSerializer
    permission_classes = [IsAuthenticated]
    queryset = Insumo.objects.all()

# Eliminar un insumo específico (si necesitas una vista separada para esto)
class InsumoEliminar(generics.DestroyAPIView):
    serializer_class = InsumoSerializer
    permission_classes = [IsAuthenticated]
    queryset = Insumo.objects.all()
