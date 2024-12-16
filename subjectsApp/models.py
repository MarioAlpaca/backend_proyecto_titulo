from django.db import models
from userApp.models import Usuario
from django.conf import settings # Importa el modelo de usuario
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from insumosApp.models import Insumo

# Create your models here.

class Asignatura(models.Model):
    nombre = models.CharField(max_length=255)
    numero_clases = models.IntegerField(default=0)
    profesor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        limit_choices_to={'rol': '2'},  # Filtra solo usuarios con rol "profesor"
        null=True,
        blank=True,
        related_name='asignaturas_impartidas'
    )
    alumnos = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        limit_choices_to={'rol': '3'},  # Filtra solo usuarios con rol "alumno"
        related_name='asignaturas_cursadas'
    )

    def __str__(self):
        return f"{self.nombre} - {self.profesor}"



class Clase(models.Model):
    ESTADOS = (
        ('pendiente', 'Pendiente'),
        ('asignada', 'Asignada'),
        ('iniciada', 'Iniciada'),
        ('finalizada', 'Finalizada'),
    )
    asignatura = models.ForeignKey(Asignatura, on_delete=models.CASCADE)
    profesor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'rol': '2'}
    )
    nombre = models.CharField(max_length=255)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    insumos_asignados = models.BooleanField(default=False)
    insumos = models.ManyToManyField(Insumo, through='ClaseInsumo')  # Nueva relación

    def __str__(self):
        return self.nombre

class ClaseInsumo(models.Model):
    clase = models.ForeignKey(Clase, on_delete=models.CASCADE)
    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2)  # Cantidad de este insumo asignada a la clase


class ClaseDistribucion(models.Model):
    clase = models.ForeignKey('subjectsApp.Clase', on_delete=models.CASCADE, related_name='distribuciones')
    alumno = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='insumos_asignados')
    insumo = models.ForeignKey('insumosApp.Insumo', on_delete=models.CASCADE)
    cantidad_asignada = models.DecimalField(max_digits=10, decimal_places=2)  # Distribución inicial
    cantidad_extra_asignada = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # Solicitudes extraordinarias
    distribuido = models.BooleanField(default=False)  # Campo opcional para control

    class Meta:
        unique_together = ('clase', 'alumno', 'insumo')
        verbose_name = 'Distribución de insumos'
        verbose_name_plural = 'Distribuciones de insumos'

    def __str__(self):
        return f"{self.cantidad_asignada} de {self.insumo.nombre} para {self.alumno.username} en {self.clase.nombre}"




class ClaseParticipacion(models.Model):
    clase = models.ForeignKey('subjectsApp.Clase', on_delete=models.CASCADE, related_name='participaciones')
    alumno = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='participaciones')
    fecha_hora_participacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('clase', 'alumno')  # Evita duplicados
        verbose_name = 'Participación en clase'
        verbose_name_plural = 'Participaciones en clases'

    def __str__(self):
        return f"Participación: {self.alumno.nombre} en {self.clase.nombre}"

class ClaseInsumoHistorial(models.Model):
    clase = models.ForeignKey('subjectsApp.Clase', on_delete=models.CASCADE, related_name='insumos_historial')
    insumo = models.ForeignKey('insumosApp.Insumo', on_delete=models.CASCADE)
    cantidad_total_asignada = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)  # Nuevo campo
    cantidad_utilizada = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cantidad_devuelta = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cantidad_extra_asignada = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)  # Nuevo campo

    def __str__(self):
        return f"Historial de {self.insumo.nombre} - Clase: {self.clase.nombre}"

class ClaseAlumnoInsumoHistorial(models.Model):
    clase = models.ForeignKey('subjectsApp.Clase', on_delete=models.CASCADE, related_name='alumno_insumo_historial')
    alumno = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    insumo = models.ForeignKey('insumosApp.Insumo', on_delete=models.CASCADE)
    cantidad_asignada = models.DecimalField(max_digits=10, decimal_places=2)
    cantidad_extra_asignada = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    

    class Meta:
        verbose_name = "Historial de insumos asignados al alumno"
        verbose_name_plural = "Historial de insumos asignados a los alumnos"

    def __str__(self):
        return f"{self.alumno.username} - {self.insumo.nombre} ({self.cantidad_asignada})"

class SolicitudInsumo(models.Model):
    ESTADOS = (
        ('pendiente', 'Pendiente'),
        ('pendiente_admin', 'Pendiente Admin'),
        ('aprobado', 'Aprobado'),
        ('rechazado', 'Rechazado'),
    )
    alumno = models.ForeignKey(Usuario, on_delete=models.CASCADE, limit_choices_to={'rol': '3'})
    clase = models.ForeignKey(Clase, on_delete=models.CASCADE)
    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE)
    cantidad_solicitada = models.DecimalField(max_digits=10, decimal_places=2)
    cantidad_aprobada = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    es_extra = models.BooleanField(default=False)  # Si se tomó del inventario general
    motivo_rechazo = models.TextField(null=True, blank=True)  # Razón del rechazo

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Solicitud de {self.alumno.nombre} para {self.insumo.nombre} ({self.estado})"

class Notificacion(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notificaciones"
    )
    mensaje = models.TextField()
    leida = models.BooleanField(default=False)  # Para marcar si la notificación fue leída
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_creacion']  # Las notificaciones más recientes primero

    def __str__(self):
        return f"Notificación para {self.usuario.username}: {self.mensaje[:30]}..."

@receiver(post_save, sender=Asignatura)
def crear_clases(sender, instance, created, **kwargs):
    if created:
        for i in range(instance.numero_clases):
            Clase.objects.create(
                asignatura=instance,
                profesor=instance.profesor,
                nombre=f"Clase {i + 1}"
            )

# Signal para actualizar el número de clases en Asignatura cuando se crea o actualiza una Clase
@receiver(post_save, sender=Clase)
def actualizar_numero_clases_post_save(sender, instance, **kwargs):
    asignatura = instance.asignatura
    asignatura.numero_clases = asignatura.clase_set.count()
    asignatura.save()


# Signal para actualizar el número de clases en Asignatura cuando se elimina una Clase
@receiver(post_delete, sender=Clase)
def actualizar_numero_clases_post_delete(sender, instance, **kwargs):
    asignatura = instance.asignatura
    asignatura.numero_clases = asignatura.clase_set.count()
    asignatura.save()



