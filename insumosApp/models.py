from django.db import models
from django.core.validators import MinValueValidator

# from subjectsApp.models import Clase

# Create your models here.
class Insumo(models.Model):
    MEDIDAS = [
        ('1', 'Kilo(s)'),
        ('2', 'Gramo(s)'),
        ('3', 'Litro(s)'),
        ('4', 'Unidad(es)'),
    ]
    nombre = models.CharField(max_length=255)
    cantidad_total = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)],
        help_text="Cantidad total del insumo (mayor o igual a 0)."
    )
    cantidad_disponible = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)],
        help_text="Cantidad disponible del insumo (mayor o igual a 0)."
    )
    unidad_medida = models.CharField(max_length=50, choices=MEDIDAS)

    def __str__(self):
        return self.nombre