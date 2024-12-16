from django.contrib import admin
from .models import Asignatura, Clase, ClaseParticipacion

# Register your models here.
admin.site.register(Asignatura)
admin.site.register(Clase)

@admin.register(ClaseParticipacion)
class ClaseParticipacionAdmin(admin.ModelAdmin):
    list_display = ('clase', 'alumno', 'fecha_hora_participacion')
    list_filter = ('clase', 'alumno')
    search_fields = ('clase__nombre', 'alumno__username')