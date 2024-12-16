from decimal import Decimal
from rest_framework import serializers
from .models import Insumo

class InsumoSerializer(serializers.ModelSerializer):
    unidad_medida_descripcion = serializers.SerializerMethodField()

    def validate_cantidad_total(self, value):
        if value < Decimal("0"):
            raise serializers.ValidationError("La cantidad total no puede ser negativa.")
        return value

    def validate_cantidad_disponible(self, value):
        if value < Decimal("0"):
            raise serializers.ValidationError("La cantidad disponible no puede ser negativa.")
        return value

    class Meta:
        model = Insumo
        fields = ['id', 'nombre', 'cantidad_total', 'unidad_medida', 'unidad_medida_descripcion']

    def get_unidad_medida_descripcion(self, obj):
        return obj.get_unidad_medida_display()
    

# class ClaseInsumoSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = ClaseInsumo
#         fields = '__all__'

# class SolicitudInsumoSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = SolicitudInsumo
#         fields = '__all__'




