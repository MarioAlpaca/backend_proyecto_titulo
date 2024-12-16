from rest_framework import serializers
from .models import Asignatura, Clase, ClaseInsumo, ClaseDistribucion, ClaseParticipacion, ClaseInsumoHistorial, SolicitudInsumo, Notificacion
from userApp.models import Usuario  # Asegúrate de tener el modelo Usuario


class AsignaturaSerializer(serializers.ModelSerializer):
    # Campos adicionales para mostrar el nombre del profesor y los nombres de los alumnos
    profesor_nombre = serializers.StringRelatedField(source='profesor', read_only=True)
    alumnos_nombres = serializers.StringRelatedField(many=True, source='alumnos', read_only=True)
    alumnos_email = serializers.StringRelatedField(many=True, source='alumnos', read_only=True)
    profesor = serializers.PrimaryKeyRelatedField(queryset=Usuario.objects.filter(rol='2'), write_only=True)
    alumnos = serializers.PrimaryKeyRelatedField(queryset=Usuario.objects.filter(rol='3'), write_only=True, many=True)
    cantidad_alumnos = serializers.SerializerMethodField()
    
    
    class Meta:
        model = Asignatura
        fields = ['id', 'nombre', 'numero_clases', 'profesor', 'alumnos', 'profesor_nombre', 'alumnos_nombres', 'cantidad_alumnos', 'alumnos_email']

    def get_cantidad_alumnos(self, obj):
        return obj.alumnos.count()

        

class ClaseInsumoSerializer(serializers.ModelSerializer):
    insumo_nombre = serializers.CharField(source='insumo.nombre', read_only=True)  # Incluye el nombre del insumo

    class Meta:
        model = ClaseInsumo
        fields = ['id', 'clase', 'insumo', 'cantidad', 'insumo_nombre']

class ClaseSerializer(serializers.ModelSerializer):
    insumos = ClaseInsumoSerializer(many=True, source='claseinsumo_set', required=False)
    ya_participa = serializers.SerializerMethodField()
    asistencia = serializers.SerializerMethodField()  # Nueva función para calcular la asistencia
    distribuciones = serializers.SerializerMethodField()
    historial_insumos = serializers.SerializerMethodField()  # Nuevo campo para mostrar insumos utilizados y devueltos

    class Meta:
        model = Clase
        fields = '__all__'

    def get_ya_participa(self, obj):
        """
        Verifica si el usuario actual ya está participando en la clase.
        """
        request = self.context.get('request')
        if request and request.user.is_authenticated and request.user.rol == "3":  # Verifica que sea un alumno
            return obj.participaciones.filter(alumno=request.user).exists()
        return False

    def get_asistencia(self, obj):
        """
        Calcula la asistencia actual para la clase en formato "participantes/total".
        """
        # Total de alumnos que han participado en la clase
        alumnos_participantes = obj.participaciones.count()
        # Total de alumnos asignados a la asignatura
        total_alumnos = obj.asignatura.alumnos.count() if obj.asignatura else 0
        return f"{alumnos_participantes}/{total_alumnos}"

    def get_distribuciones(self, obj):
        """
        Devuelve las distribuciones de insumos en la clase, incluyendo tanto los insumos asignados inicialmente
        como los extras que hayan sido solicitados y aprobados.
        """
        distribuciones = ClaseDistribucion.objects.filter(clase=obj).select_related('alumno', 'insumo')
        return [
            {
                "alumno": distribucion.alumno.nombre,
                "insumo": distribucion.insumo.nombre,
                "cantidad_asignada": distribucion.cantidad_asignada,
                "cantidad_extra_asignada": distribucion.cantidad_extra_asignada,  # Asegúrate de incluir este campo
            }
            for distribucion in distribuciones
        ]


    def get_historial_insumos(self, obj):
        """
        Devuelve el historial de insumos de la clase (utilizados y devueltos al inventario).
        """
        if obj.estado == "finalizada":
            historial = ClaseInsumoHistorial.objects.filter(clase=obj).select_related('insumo')
            serializer = ClaseInsumoHistorialSerializer(historial, many=True)
            return serializer.data
        return None



class ClaseParticipacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClaseParticipacion
        fields = ['id', 'clase', 'alumno', 'fecha_hora_participacion']


class ClaseInsumoHistorialSerializer(serializers.ModelSerializer):
    insumo_nombre = serializers.CharField(source='insumo.nombre')
    unidad_medida = serializers.CharField(source='insumo.get_unidad_medida_display')

    class Meta:
        model = ClaseInsumoHistorial
        fields = ['insumo_nombre', 'unidad_medida', 'cantidad_total_asignada', 'cantidad_utilizada', 'cantidad_devuelta', 'cantidad_extra_asignada']

class SolicitudInsumoSerializer(serializers.ModelSerializer):
    alumno_nombre = serializers.StringRelatedField(source="alumno.username")
    clase_nombre = serializers.StringRelatedField(source="clase.nombre")

    class Meta:
        model = SolicitudInsumo
        fields = '__all__'


class NotificacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notificacion
        fields = ['id', 'usuario', 'mensaje', 'leida', 'fecha_creacion']