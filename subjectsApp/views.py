from django.shortcuts import render
from rest_framework import viewsets
from userApp.permissions import IsProfesor, IsAdmin, IsEstudiante, IsProfesorOrAdmin
from rest_framework.permissions import AllowAny, IsAuthenticated
from .models import Asignatura, Clase, ClaseParticipacion, ClaseDistribucion, ClaseInsumoHistorial, ClaseAlumnoInsumoHistorial, SolicitudInsumo, Notificacion
from .serializers import AsignaturaSerializer, ClaseSerializer, ClaseInsumoHistorialSerializer, SolicitudInsumoSerializer, NotificacionSerializer
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Asignatura, Clase, ClaseInsumo
from rest_framework import viewsets, status
from insumosApp.models import Insumo
from django.db import transaction
from django.db.models import Sum
from decimal import Decimal
from django.db.models import F, Count
from userApp.models import Usuario
from decimal import Decimal  # Asegúrate de importar Decimal

# Create your views here.
def distribuir_insumos(clase):
    """
    Distribuye insumos proporcionalmente a los alumnos que participan en la clase.
    Los insumos no asignados permanecen en la clase.
    """
    # Obtener participantes y los insumos asignados a la clase
    participantes = ClaseParticipacion.objects.filter(clase=clase).select_related('alumno')
    insumos_asignados = ClaseInsumo.objects.filter(clase=clase)

    # Validar que haya insumos asignados a la clase
    if not insumos_asignados.exists():
        return

    # Obtener números totales de alumnos y participantes
    total_alumnos_clase = clase.asignatura.alumnos.count()  # Número total de alumnos en la asignatura
    total_participantes = participantes.count()

    if total_participantes == 0:
        # Si no hay participantes, no se realiza la distribución
        return

    for insumo_asignado in insumos_asignados:
        # Calcular la cantidad total disponible para el insumo
        cantidad_total = insumo_asignado.cantidad

        # Evitar divisiones por cero si no hay alumnos asignados a la clase
        if total_alumnos_clase == 0:
            continue

        # Calcular la cantidad asignable por alumno
        cantidad_por_alumno = cantidad_total / Decimal(total_alumnos_clase)

        # Distribuir entre los participantes
        for participacion in participantes:
            alumno = participacion.alumno
            distribucion, created = ClaseDistribucion.objects.get_or_create(
                clase=clase,
                alumno=alumno,
                insumo=insumo_asignado.insumo,
                defaults={"cantidad_asignada": round(cantidad_por_alumno, 2)}
            )
            if not created:
                distribucion.cantidad_asignada = round(cantidad_por_alumno, 2)
                distribucion.save()

        # Calcular la cantidad restante no distribuida
        cantidad_distribuida = cantidad_por_alumno * Decimal(total_participantes)
        cantidad_restante = cantidad_total - cantidad_distribuida

        # Actualizar la cantidad restante en el insumo de la clase
        insumo_asignado.cantidad = max(cantidad_restante, 0)
        insumo_asignado.save()



class AsignaturaView(viewsets.ModelViewSet):
    serializer_class = AsignaturaSerializer
    permission_classes = [IsAuthenticated]


    def get_queryset(self):
        user = self.request.user
        # Si el usuario es profesor, mostramos solo sus asignaturas
        if user.rol == "2":  # Rol de profesor
            return Asignatura.objects.filter(profesor=user)
        elif user.rol == "3":  # Rol de alumno
            return Asignatura.objects.filter(alumnos=user)  # Filtra por alumnos asignados
        elif user.rol == "1":  # Rol de administrador
            return Asignatura.objects.all()
        # Si el usuario no es admin, profesor ni alumno, no devuelve asignaturas
        return Asignatura.objects.none()

    
    @action(detail=True, methods=['get'], url_path='clases')
    def obtener_clases(self, request, pk=None):
        """
        Devuelve todas las clases asociadas a una asignatura específica,
        junto con el número actualizado de clases.
        """
        asignatura = self.get_object()

        # Verificar si el usuario es profesor y si es el profesor asignado a esta asignatura
        if request.user.rol == "2" and asignatura.profesor != request.user:
            raise PermissionDenied("No tienes permiso para ver estas clases.")

        clases = Clase.objects.filter(asignatura=asignatura)
        
        # Pasar el contexto del request al serializador
        serializer = ClaseSerializer(clases, many=True, context={'request': request})

        return Response({
            'clases': serializer.data,
            'numero_clases': clases.count()
        })

    @action(detail=True, methods=['post'], url_path='agregar_clase')
    def agregar_clase(self, request, pk=None):
        """
        Agrega una nueva clase a la asignatura específica y devuelve
        la clase creada junto con el número actualizado de clases.
        """
        asignatura = self.get_object()
        nombre = request.data.get("nombre", f"Clase {asignatura.clase_set.count() + 1}")
        estado = request.data.get("estado", "pendiente")
        profesor = asignatura.profesor

        try:
            nueva_clase = Clase.objects.create(
                asignatura=asignatura,
                nombre=nombre,
                estado=estado,
                profesor=profesor
            )
            serializer = ClaseSerializer(nueva_clase)
            
            # Retornar la nueva clase y el número de clases actualizado
            return Response({
                'clase': serializer.data,
                'numero_clases': asignatura.clase_set.count()
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    
    def perform_create(self, serializer):
        """
        Crea la asignatura y añade al menos una clase por defecto.
        """
        asignatura = serializer.save()
        if asignatura.clase_set.count() == 0:
            Clase.objects.create(
                asignatura=asignatura,
                nombre="Clase 1",
                profesor=asignatura.profesor
            )

    def update(self, request, *args, **kwargs):
        """
        Actualiza la asignatura, sin cambiar manualmente el número de clases.
        """
        response = super().update(request, *args, **kwargs)
        asignatura = self.get_object()
        
        # Sincronización explícita de `numero_clases`
        asignatura.numero_clases = asignatura.clase_set.count()
        asignatura.save()  # Guarda el cambio en la base de datos   
        
        # Retornar la asignatura actualizada con el nuevo número de clases
        return Response({
            'asignatura': AsignaturaSerializer(asignatura).data,
            'numero_clases': asignatura.numero_clases
        })

    def destroy(self, request, *args, **kwargs):
        """
        Sobrescribe el método destroy para devolver los insumos al inventario general
        al eliminar una asignatura, excepto para clases en estado 'iniciada' o 'finalizada'.
        """
        asignatura = self.get_object()
        clases = Clase.objects.filter(asignatura=asignatura)

        with transaction.atomic():  # Aseguramos la consistencia en caso de errores
            for clase in clases:
                if clase.estado not in ["iniciada", "finalizada"]:
                    # Devolver insumos al inventario general
                    insumos_clase = ClaseInsumo.objects.filter(clase=clase)
                    for insumo_clase in insumos_clase:
                        insumo = insumo_clase.insumo
                        insumo.cantidad_total += insumo_clase.cantidad  # Devolver la cantidad asignada
                        insumo.save()
                        insumo_clase.delete()  # Eliminar la relación ClaseInsumo

                # Eliminar la clase
                clase.delete()

            # Eliminar la asignatura
            self.perform_destroy(asignatura)

        return Response({"status": "Asignatura eliminada correctamente"}, status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['get'], url_path='reporte_participacion', permission_classes=[IsAdmin])
    def reporte_participacion(self, request, pk=None):
        """
        Reporte de participación de alumnos en una asignatura.
        """
        asignatura = self.get_object()
        alumnos = asignatura.alumnos.all()

        data = []
        for alumno in alumnos:
            total_clases = asignatura.clase_set.count()
            clases_participadas = ClaseParticipacion.objects.filter(clase__asignatura=asignatura, alumno=alumno).count()

            porcentaje_participacion = (
                (clases_participadas / total_clases) * 100 if total_clases > 0 else 0
            )
            data.append({
                "alumno": alumno.nombre,
                "email": alumno.email,
                "participacion": porcentaje_participacion,
                "clases_participadas": clases_participadas,
                "total_clases": total_clases
            })

        return Response({"participacion": data}, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'], url_path='reporte_participacion_general', permission_classes=[IsAdmin])
    def reporte_participacion_general(self, request):
        """
        Reporte de participación por asignatura para todos los alumnos.
        """
        asignaturas = Asignatura.objects.prefetch_related("clase_set", "alumnos").all()

        data = []
        for asignatura in asignaturas:
            total_clases = asignatura.clase_set.count()
            total_participaciones = ClaseParticipacion.objects.filter(clase__asignatura=asignatura).count()
            total_alumnos = asignatura.alumnos.count()

            porcentaje_general = (
                (total_participaciones / (total_clases * total_alumnos)) * 100
                if total_clases > 0 and total_alumnos > 0
                else 0
            )

            data.append({
                "asignatura": asignatura.nombre,
                "profesor": asignatura.profesor.nombre if asignatura.profesor else "Sin profesor asignado",
                "porcentaje": round(porcentaje_general, 2),
                "total_clases": total_clases,
                "total_alumnos": total_alumnos,
                "total_participaciones": total_participaciones
            })

        return Response({"reporte": data}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='reporte_participacion_alumno', permission_classes=[IsAuthenticated])
    def reporte_participacion_alumno(self, request):
        """
        Reporte de participación del alumno en todas las asignaturas.
        """
        alumno_id = request.query_params.get('alumno_id')
        if not alumno_id:
            return Response({"error": "Se requiere el ID del alumno."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            alumno = Usuario.objects.get(id=alumno_id, rol=3)  # Corrige 'role' a 'rol' y verifica que sea un alumno
        except Usuario.DoesNotExist:
            return Response({"error": "Alumno no encontrado o no es un alumno."}, status=status.HTTP_404_NOT_FOUND)

        asignaturas = alumno.asignaturas_cursadas.all()
        data = []

        for asignatura in asignaturas:
            total_clases = asignatura.clase_set.count()
            clases_participadas = ClaseParticipacion.objects.filter(clase__asignatura=asignatura, alumno=alumno).count()

            porcentaje_participacion = (
                (clases_participadas / total_clases) * 100 if total_clases > 0 else 0
            )

            data.append({
                "asignatura": asignatura.nombre,
                "porcentaje_participacion": round(porcentaje_participacion, 2),
                "clases_participadas": clases_participadas,
                "total_clases": total_clases,
            })

        return Response({"participacion": data}, status=status.HTTP_200_OK)





class ClaseViewSet(viewsets.ModelViewSet):
    queryset = Clase.objects.all()
    serializer_class = ClaseSerializer
    permission_classes = [AllowAny]

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, context={'request': request})
        return Response(serializer.data)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], permission_classes=[IsProfesor])
    def cambiar_estado(self, request, pk=None):
        """
        Permite que el profesor cambie el estado de la clase de 'asignada' a 'iniciada' o de 'iniciada' a 'finalizada'.
        """
        clase = self.get_object()
        nuevo_estado = request.data.get('estado')

        # Verificar si se envió el estado
        if not nuevo_estado:
            return Response({'error': 'El campo "estado" es obligatorio.'}, status=status.HTTP_400_BAD_REQUEST)

        # Verificar la transición de estado
        if (clase.estado == 'asignada' and nuevo_estado == 'iniciada') or (clase.estado == 'iniciada' and nuevo_estado == 'finalizada'):
            clase.estado = nuevo_estado
            clase.save()

            # Agregar la lógica de distribuir insumos si el estado cambia a 'iniciada'
            if nuevo_estado == 'iniciada':
                try:
                    distribuir_insumos(clase)  # Asegúrate de que esta función está correctamente definida
                except Exception as e:
                    return Response({'error': f'Error al distribuir insumos: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            return Response({'status': 'Estado actualizado'}, status=status.HTTP_200_OK)

        # Si la transición no es válida
        return Response({'error': 'Transición de estado no permitida'}, status=status.HTTP_400_BAD_REQUEST)



    @action(detail=True, methods=['post'], url_path='asignar_insumos')
    def asignar_insumos(self, request, pk=None):
        """
        Asigna varios insumos a una clase y actualiza el inventario general.
        """
        clase = self.get_object()
        insumos_data = request.data.get('insumos', [])

        if not insumos_data:
            return Response({'error': 'No se han proporcionado insumos para asignar.'}, status=status.HTTP_400_BAD_REQUEST)

        errores = []
        with transaction.atomic():
            for insumo_data in insumos_data:
                insumo_id = insumo_data.get('insumo_id')
                cantidad = insumo_data.get('cantidad')

                # Validar que insumo_id sea un número entero y cantidad sea un número positivo
                if not isinstance(insumo_id, int) or not isinstance(cantidad, (int, float, Decimal)) or cantidad <= 0:
                    errores.append(f"Datos inválidos para insumo: {insumo_data}")
                    continue

                try:
                    insumo = Insumo.objects.get(id=insumo_id)

                    # Convertir cantidad a Decimal
                    cantidad = Decimal(str(cantidad))

                    if insumo.cantidad_total >= cantidad:
                        # Actualizar inventario y asignar insumo
                        insumo.cantidad_total -= cantidad
                        insumo.save()

                        # Actualizar o crear ClaseInsumo
                        clase_insumo, created = ClaseInsumo.objects.get_or_create(
                            clase=clase,
                            insumo=insumo,
                            defaults={'cantidad': cantidad},
                        )
                        if not created:
                            clase_insumo.cantidad += cantidad
                            clase_insumo.save()
                    else:
                        errores.append(f"Cantidad insuficiente para el insumo '{insumo.nombre}'. Disponible: {insumo.cantidad_total}. Solicitado: {cantidad}.")
                except Insumo.DoesNotExist:
                    errores.append(f"Insumo con ID {insumo_id} no encontrado.")
                except Exception as e:
                    errores.append(f"Error procesando el insumo con ID {insumo_id}: {str(e)}")

            if errores:
                return Response({'error': 'Algunos insumos no pudieron asignarse', 'detalles': errores}, status=status.HTTP_400_BAD_REQUEST)

        clase.estado = 'asignada'
        clase.insumos_asignados = True
        clase.save()

        return Response({'status': 'Insumos asignados correctamente.'}, status=status.HTTP_200_OK)




    
    @action(detail=True, methods=['get'], url_path='insumos_asignados')
    def insumos_asignados(self, request, pk=None):
        """
        Devuelve los insumos asignados a una clase, incluyendo cantidad total asignada,
        cantidad repartida y cantidad restante.
        """
        clase = self.get_object()

        # Crear un diccionario para mapear las unidades de medida
        unidad_medida_dict = dict(Insumo.MEDIDAS)  # Convertir choices a un diccionario

        # Obtener todos los insumos asignados a la clase
        insumos = ClaseInsumo.objects.filter(clase=clase)

        # Construir la respuesta con cálculos de cantidades
        insumos_data = []
        for insumo_clase in insumos:
            # Calcular la cantidad repartida, excluyendo las aprobaciones extraordinarias
            cantidad_repartida = (
                ClaseDistribucion.objects.filter(
                    clase=clase,
                    insumo=insumo_clase.insumo,
                    alumno__isnull=False  # Excluir cualquier distribución genérica o extraordinaria
                )
                .aggregate(total=Sum('cantidad_asignada'))['total'] or 0
            )

            # Calcular la cantidad restante
            cantidad_restante = insumo_clase.cantidad - cantidad_repartida

            # Prevenir resultados negativos en cantidad restante
            cantidad_restante = max(0, cantidad_restante)

            # Agregar los datos del insumo a la respuesta
            insumos_data.append({
                'id': insumo_clase.insumo.id,
                'nombre': insumo_clase.insumo.nombre,
                'unidad_medida': unidad_medida_dict.get(insumo_clase.insumo.unidad_medida, "Desconocido"),
                'total_cantidad': insumo_clase.cantidad,  # Cantidad total asignada a la clase
                'cantidad_repartida': round(cantidad_repartida, 2),  # Cantidad distribuida entre alumnos
                'cantidad_restante': round(cantidad_restante, 2),  # Cantidad aún no distribuida
            })

        return Response({'insumos': insumos_data}, status=status.HTTP_200_OK)




    
    @action(detail=True, methods=['post'], url_path='quitar_insumos')
    def quitar_insumos(self, request, pk=None):
        """
        Quita una cantidad específica de un insumo asignado a la clase o elimina el insumo completamente.
        """
        clase = self.get_object()
        insumo_id = request.data.get('insumo_id')
        cantidad_a_quitar = request.data.get('cantidad', 0)

        try:
            # Convertir cantidad_a_quitar a Decimal
            cantidad_a_quitar = Decimal(str(cantidad_a_quitar))
        except (ValueError, TypeError):
            return Response({'error': 'Cantidad a quitar inválida. Debe ser un número positivo.'}, status=status.HTTP_400_BAD_REQUEST)

        # Bloquear si la clase está en estado 'iniciada' o 'finalizada'
        if clase.estado in ["iniciada", "finalizada"]:
            return Response({'error': 'No se pueden quitar insumos de una clase en estado iniciado o finalizado.'},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                clase_insumos = ClaseInsumo.objects.filter(clase=clase, insumo_id=insumo_id)
                
                # Sumar la cantidad total disponible en las múltiples entradas
                total_cantidad_asignada = sum(ci.cantidad for ci in clase_insumos)

                # Validar si la cantidad a quitar es válida
                if cantidad_a_quitar <= 0 or cantidad_a_quitar > total_cantidad_asignada:
                    return Response({'error': 'Cantidad a quitar inválida.'}, status=status.HTTP_400_BAD_REQUEST)

                cantidad_restante = cantidad_a_quitar

                # Recorrer cada entrada de ClaseInsumo y reducir la cantidad o eliminar la entrada
                for clase_insumo in clase_insumos:
                    if cantidad_restante <= 0:
                        break

                    if clase_insumo.cantidad <= cantidad_restante:
                        # Si la cantidad en esta entrada es menor o igual a la cantidad restante, elimínala
                        cantidad_restante -= clase_insumo.cantidad
                        clase_insumo.delete()
                    else:
                        # Si la cantidad en esta entrada es mayor, solo reduce la cantidad
                        clase_insumo.cantidad -= cantidad_restante
                        clase_insumo.save()
                        cantidad_restante = Decimal(0)

                # Actualizar el inventario general del insumo
                insumo = Insumo.objects.get(id=insumo_id)
                insumo.cantidad_total += cantidad_a_quitar
                insumo.save()

                return Response({'status': 'Insumo actualizado correctamente.'}, status=status.HTTP_200_OK)

        except Insumo.DoesNotExist:
            return Response({'error': 'Insumo no encontrado en el inventario general.'}, status=status.HTTP_404_NOT_FOUND)
        except ClaseInsumo.DoesNotExist:
            return Response({'error': 'Insumo no asignado a la clase.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': f'Error al quitar insumos: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], url_path='participar', permission_classes=[IsAuthenticated])
    def participar(self, request, pk=None):
        """
        Registra la participación de un alumno en una clase y distribuye insumos si hay disponibles.
        """
        clase = self.get_object()
        alumno_id = request.data.get("alumno_id")  # Obtener el ID del alumno desde el request, si está presente

        try:
            # Si no se proporciona un alumno_id, usar el usuario autenticado
            if not alumno_id:
                alumno = request.user
                if alumno.rol != "3":  # Verificar que el usuario sea un alumno
                    return Response({"error": "Solo los alumnos pueden participar en clases."}, status=status.HTTP_403_FORBIDDEN)
            else:
                # Si se proporciona alumno_id, verificar su existencia
                alumno = Usuario.objects.get(id=alumno_id, rol="3")

            # Verificar que la clase esté en estado "iniciada"
            if clase.estado != "iniciada":
                return Response({"error": "La clase no está iniciada. No puedes participar todavía."}, status=status.HTTP_400_BAD_REQUEST)

            with transaction.atomic():
                # Crear participación si no existe
                participacion, created = ClaseParticipacion.objects.get_or_create(clase=clase, alumno=alumno)

                if not created:
                    return Response({"status": "Ya estás participando en esta clase."}, status=status.HTTP_200_OK)

                # Obtener insumos asignados a la clase
                insumos_clase = ClaseInsumo.objects.filter(clase=clase)

                # Total de alumnos asignados a la asignatura
                total_alumnos = clase.asignatura.alumnos.count()

                for insumo_clase in insumos_clase:
                    # Cantidad asignada por alumno
                    cantidad_por_alumno = insumo_clase.cantidad / Decimal(total_alumnos)

                    # Verificar si ya se distribuyó al alumno
                    distribucion, created = ClaseDistribucion.objects.get_or_create(
                        clase=clase,
                        alumno=alumno,
                        insumo=insumo_clase.insumo,
                        defaults={"cantidad_asignada": cantidad_por_alumno},
                    )

                    if created:
                        distribucion.cantidad_asignada = cantidad_por_alumno
                        distribucion.save()

            return Response({"status": "Participación registrada y los insumos se distribuyeron correctamente."}, status=status.HTTP_200_OK)

        except Usuario.DoesNotExist:
            return Response({"error": "El alumno especificado no existe o no tiene el rol de alumno."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"No se pudo registrar la participación: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)




    def destroy(self, request, *args, **kwargs):
        """
        Elimina una clase. Devuelve los insumos asignados al inventario general
        si la clase no está en estado 'iniciada' o 'finalizada'.
        """
        clase = self.get_object()

        # Bloquear si la clase está en estado 'iniciada' o 'finalizada'
        if clase.estado in ["iniciada", "finalizada"]:
            return Response({'error': 'No se puede eliminar una clase en estado iniciado o finalizado.'},
                            status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():  # Asegurar consistencia
            # Devolver insumos al inventario general
            insumos_clase = ClaseInsumo.objects.filter(clase=clase)
            for insumo_clase in insumos_clase:
                insumo = insumo_clase.insumo
                insumo.cantidad_total += insumo_clase.cantidad  # Devolver la cantidad asignada
                insumo.save()
                insumo_clase.delete()  # Eliminar la relación ClaseInsumo

            # Eliminar la clase
            self.perform_destroy(clase)

        return Response({"status": "Clase eliminada correctamente"}, status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['get'], url_path='mis_insumos', permission_classes=[IsEstudiante])
    def mis_insumos(self, request, pk=None):
        """
        Devuelve los insumos distribuidos a un alumno en una clase específica.
        """
        clase = self.get_object()
        alumno = request.user

        # Validar que el usuario sea un alumno
        if alumno.rol != "3":
            return Response({"error": "Solo los alumnos pueden consultar sus insumos."}, status=status.HTTP_403_FORBIDDEN)

        distribuciones = ClaseDistribucion.objects.filter(clase=clase, alumno=alumno)

        data = [
            {
                "insumo": distribucion.insumo.nombre,
                "cantidad_asignada": distribucion.cantidad_asignada,
                "cantidad_extra_asignada": distribucion.cantidad_extra_asignada,  # Asegúrate de incluir este campo
                "unidad_medida": distribucion.insumo.get_unidad_medida_display(),
            }
            for distribucion in distribuciones
        ]

        return Response({"insumos": data}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='finalizar_clase', permission_classes=[IsProfesor])
    def finalizar_clase(self, request, pk=None):
        """
        Finaliza una clase, devolviendo los insumos no utilizados al inventario general
        y registrando el historial de la clase y los insumos asignados a los alumnos.
        Además, rechaza las solicitudes pendientes al finalizar la clase.
        """
        clase = self.get_object()

        if clase.estado != "iniciada":
            return Response(
                {"error": "Solo se pueden finalizar clases en estado 'iniciada'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with transaction.atomic():
                insumos_clase = ClaseInsumo.objects.filter(clase=clase)

                # Registrar los insumos asignados a los alumnos
                distribuciones = ClaseDistribucion.objects.filter(clase=clase)
                for distribucion in distribuciones:
                    # Registrar la cantidad asignada y la cantidad extra por separado
                    ClaseAlumnoInsumoHistorial.objects.create(
                        clase=clase,
                        alumno=distribucion.alumno,
                        insumo=distribucion.insumo,
                        cantidad_asignada=distribucion.cantidad_asignada,
                        cantidad_extra_asignada=distribucion.cantidad_extra_asignada or 0  # Asegurarnos de que no sea None
                    )

                for insumo_clase in insumos_clase:
                    # Cantidad total asignada a la clase
                    cantidad_total_asignada = insumo_clase.cantidad

                    # Cantidad distribuida entre los alumnos
                    cantidad_distribuida = ClaseDistribucion.objects.filter(
                        clase=clase, insumo=insumo_clase.insumo
                    ).aggregate(total=Sum('cantidad_asignada'))['total'] or 0

                    # Cantidad extra distribuida entre los alumnos
                    cantidad_extra_distribuida = ClaseDistribucion.objects.filter(
                        clase=clase, insumo=insumo_clase.insumo
                    ).aggregate(total=Sum('cantidad_extra_asignada'))['total'] or 0

                    # Cantidad no utilizada (asegurarnos de que no sea negativa)
                    cantidad_no_utilizada = max(cantidad_total_asignada - cantidad_distribuida, 0)

                    # Registrar en el historial general
                    ClaseInsumoHistorial.objects.create(
                        clase=clase,
                        insumo=insumo_clase.insumo,
                        cantidad_total_asignada=cantidad_total_asignada,
                        cantidad_utilizada=cantidad_distribuida,
                        cantidad_devuelta=cantidad_no_utilizada,
                        cantidad_extra_asignada=cantidad_extra_distribuida
                    )

                    # Devolver al inventario general solo lo no utilizado
                    if cantidad_no_utilizada > 0:
                        insumo_clase.insumo.cantidad_total += cantidad_no_utilizada
                        insumo_clase.insumo.save()

                    # Eliminar el insumo asignado a la clase
                    insumo_clase.delete()

                # Eliminar las distribuciones después de registrarlas en el historial
                distribuciones.delete()

                # Rechazar solicitudes pendientes
                solicitudes_pendientes = SolicitudInsumo.objects.filter(clase=clase, estado="pendiente")
                for solicitud in solicitudes_pendientes:
                    solicitud.estado = "rechazado"
                    solicitud.motivo_rechazo = "La clase ha finalizado."
                    solicitud.save()

                    # Crear notificación para el alumno
                    Notificacion.objects.create(
                        usuario=solicitud.alumno,
                        mensaje=f"Tu solicitud de {solicitud.cantidad_solicitada} {solicitud.insumo.nombre} ha sido rechazada porque la clase ha finalizado.",
                    )

                # Cambiar el estado de la clase
                clase.estado = "finalizada"
                clase.save()

            return Response(
                {"status": "Clase finalizada. Historial de insumos asignados y utilizados registrado. Solicitudes pendientes rechazadas."},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response({"error": f"Error al finalizar la clase: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


        
    @action(detail=True, methods=['get'], url_path='historial_insumos', permission_classes=[IsAuthenticated])
    def historial_insumos(self, request, pk=None):
        """
        Devuelve el historial de insumos utilizados y devueltos para una clase finalizada.
        """
        clase = self.get_object()

        # Validar que el usuario sea un profesor o administrador autorizado
        if request.user.rol not in ["1", "2"]:  # "1" para admin, "2" para profesor
            return Response(
                {"error": "Solo los administradores o profesores pueden consultar el historial de insumos."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Validar que la clase esté finalizada
        if clase.estado != "finalizada":
            return Response(
                {"error": "Solo se puede consultar el historial de clases finalizadas."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Obtener el historial de insumos
        historial = ClaseInsumoHistorial.objects.filter(clase=clase)
        data = [
            {
                "insumo": registro.insumo.nombre,
                "cantidad_total_asignada": registro.cantidad_total_asignada,
                "cantidad_utilizada": registro.cantidad_utilizada,
                "cantidad_devuelta": registro.cantidad_devuelta,
                "cantidad_extra_asignada": registro.cantidad_extra_asignada,
                "unidad_medida": registro.insumo.get_unidad_medida_display(),
                
            }
            for registro in historial
        ]

        return Response({"insumos": data}, status=status.HTTP_200_OK)


    
    @action(detail=True, methods=['get'], url_path='historial_insumos_alumno', permission_classes=[IsEstudiante])
    def historial_insumos_alumno(self, request, pk=None):
        clase = self.get_object()
        alumno = request.user

        # Validar que el usuario es un estudiante
        if alumno.rol != "3":
            return Response({"error": "Solo los alumnos pueden consultar su historial de insumos."}, status=status.HTTP_403_FORBIDDEN)

        # Validar que la clase haya finalizado
        if clase.estado != "finalizada":
            return Response(
                {"error": "El historial de insumos solo está disponible para clases finalizadas."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Consultar el historial de insumos asignados al alumno
        historial = ClaseAlumnoInsumoHistorial.objects.filter(clase=clase, alumno=alumno)
        data = [
            {
                "insumo": registro.insumo.nombre,
                "cantidad_asignada": registro.cantidad_asignada,  # Cantidad asignada originalmente
                "cantidad_extra_asignada": registro.cantidad_extra_asignada,  # Cantidad extra solicitada
                "unidad_medida": registro.insumo.get_unidad_medida_display(),
            }
            for registro in historial
        ]

        return Response({"insumos": data}, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], url_path='solicitar_insumo', permission_classes=[IsEstudiante])
    def solicitar_insumo(self, request, pk=None):
        """
        Permite al alumno solicitar insumos. La cantidad solicitada no puede exceder la cantidad asignada al alumno.
        """
        clase = self.get_object()
        alumno = request.user

        if alumno.rol != "3":
            return Response({"error": "Solo los alumnos pueden solicitar insumos."}, status=status.HTTP_403_FORBIDDEN)

        solicitudes = request.data.get('solicitudes', [])
        if not isinstance(solicitudes, list):
            return Response({"error": "Las solicitudes deben ser un arreglo."}, status=status.HTTP_400_BAD_REQUEST)

        respuestas = []
        for solicitud in solicitudes:
            insumo_id = solicitud.get('insumoId')
            cantidad_solicitada = Decimal(solicitud.get('cantidadSolicitada', 0))

            try:
                insumo = Insumo.objects.get(nombre=insumo_id)

                if cantidad_solicitada <= 0:
                    respuestas.append({"insumoId": insumo_id, "error": "Cantidad solicitada inválida."})
                    continue

                # Verificar la cantidad asignada al alumno
                distribucion = ClaseDistribucion.objects.filter(
                    clase=clase, alumno=alumno, insumo=insumo
                ).first()

                if not distribucion:
                    respuestas.append({"insumoId": insumo_id, "error": "No tienes insumos asignados de este tipo."})
                    continue

                if cantidad_solicitada > distribucion.cantidad_asignada:
                    respuestas.append({"insumoId": insumo_id, "error": "La cantidad solicitada excede tu asignación."})
                    continue

                # Crear la solicitud con estado "pendiente"
                SolicitudInsumo.objects.create(
                    alumno=alumno,
                    clase=clase,
                    insumo=insumo,
                    cantidad_solicitada=cantidad_solicitada,
                    estado="pendiente"
                )
                respuestas.append({"insumoId": insumo_id, "status": "Solicitud creada correctamente."})

            except Insumo.DoesNotExist:
                respuestas.append({"insumoId": insumo_id, "error": "El insumo solicitado no existe."})

        return Response(respuestas, status=status.HTTP_200_OK)

    
    @action(detail=False, methods=['get'], url_path='reporte_insumos', permission_classes=[IsAdmin])
    def reporte_insumos(self, request):
        """
        Reporte de historial de insumos con datos agregados.
        """
        historial = ClaseInsumoHistorial.objects.select_related('clase', 'clase__asignatura', 'insumo')
        data = [
            {
                "insumo": registro.insumo.nombre,
                "asignatura": registro.clase.asignatura.nombre,
                "clase": registro.clase.nombre,
                "cantidad_total": registro.cantidad_total_asignada,
                "cantidad_utilizada": registro.cantidad_utilizada,
                "cantidad_devuelta": registro.cantidad_devuelta,
                "cantidad_extra": registro.cantidad_extra_asignada
            }
            for registro in historial
        ]
        return Response({"historial": data}, status=status.HTTP_200_OK)



class SolicitudInsumoViewSet(viewsets.ModelViewSet):
    queryset = SolicitudInsumo.objects.all()
    serializer_class = SolicitudInsumoSerializer

    @action(detail=True, methods=['post'], url_path='gestionar_solicitud', permission_classes=[IsAuthenticated])
    def gestionar_solicitud(self, request, pk=None):
        """
        Gestiona la solicitud de insumo (aprobar o rechazar).
        """
        try:
            solicitud = SolicitudInsumo.objects.get(id=pk)

            accion = request.data.get("accion")  # "aprobar" o "rechazar"
            user = request.user

            if user.rol == "2":  # Profesor
                if solicitud.estado != "pendiente":
                    return Response({"error": "Solo puedes gestionar solicitudes en estado 'pendiente'."}, status=status.HTTP_403_FORBIDDEN)

                if accion == "aprobar":
                    # Cambiar estado a pendiente_admin
                    solicitud.estado = "pendiente_admin"
                    solicitud.save()
                    return Response({"status": "Solicitud aprobada por el profesor y enviada al administrador."}, status=status.HTTP_200_OK)

                elif accion == "rechazar":
                    # Cambiar estado a rechazado y notificar al alumno
                    solicitud.estado = "rechazado"
                    solicitud.motivo_rechazo = request.data.get("motivo", "Sin motivo proporcionado.")
                    solicitud.save()

                    Notificacion.objects.create(
                        usuario=solicitud.alumno,
                        mensaje=f"Tu solicitud de {solicitud.cantidad_solicitada} {solicitud.insumo.nombre} ha sido rechazada por el profesor."
                    )
                    return Response({"status": "Solicitud rechazada por el profesor."}, status=status.HTTP_200_OK)

            elif user.rol == "1":  # Administrador
                if solicitud.estado != "pendiente_admin":
                    return Response({"error": "Solo puedes gestionar solicitudes en estado 'pendiente_admin'."}, status=status.HTTP_403_FORBIDDEN)

                if accion == "aprobar":
                    cantidad_aprobada = solicitud.cantidad_solicitada

                    if solicitud.insumo.cantidad_total < cantidad_aprobada:
                        return Response(
                            {"error": f"Inventario general insuficiente. Disponible: {solicitud.insumo.cantidad_total}, solicitado: {cantidad_aprobada}."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    # Reducir del inventario general
                    solicitud.insumo.cantidad_total -= cantidad_aprobada
                    solicitud.insumo.save()

                    # Registrar como cantidad extra asignada al alumno
                    distribucion, created = ClaseDistribucion.objects.get_or_create(
                        clase=solicitud.clase,
                        alumno=solicitud.alumno,
                        insumo=solicitud.insumo,
                        defaults={"cantidad_asignada": 0, "cantidad_extra_asignada": 0}
                    )
                    distribucion.cantidad_extra_asignada += cantidad_aprobada
                    distribucion.save()

                    # Cambiar estado a aprobado y notificar al alumno
                    solicitud.estado = "aprobado"
                    solicitud.save()

                    Notificacion.objects.create(
                        usuario=solicitud.alumno,
                        mensaje=f"Tu solicitud de {cantidad_aprobada} {solicitud.insumo.nombre} ha sido aprobada por el administrador."
                    )
                    return Response({"status": "Solicitud aprobada por el administrador."}, status=status.HTTP_200_OK)

                elif accion == "rechazar":
                    # Cambiar estado a rechazado y notificar al alumno
                    solicitud.estado = "rechazado"
                    solicitud.motivo_rechazo = request.data.get("motivo", "Sin motivo proporcionado.")
                    solicitud.save()

                    Notificacion.objects.create(
                        usuario=solicitud.alumno,
                        mensaje=f"Tu solicitud de {solicitud.cantidad_solicitada} {solicitud.insumo.nombre} ha sido rechazada por el administrador."
                    )
                    return Response({"status": "Solicitud rechazada por el administrador."}, status=status.HTTP_200_OK)

            return Response({"error": "Acción inválida. Debe ser 'aprobar' o 'rechazar'."}, status=status.HTTP_400_BAD_REQUEST)

        except SolicitudInsumo.DoesNotExist:
            return Response({"error": "La solicitud no existe."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Error al procesar la solicitud: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




    @action(detail=False, methods=['get'], url_path='profesor', permission_classes=[IsProfesor])
    def solicitudes_profesor(self, request):
        """
        Devuelve las solicitudes asignadas a un profesor específico,
        excluyendo las solicitudes extraordinarias.
        """
        profesor = request.user

        # Filtrar solo las solicitudes normales (es_extra=False) que estén pendientes
        solicitudes = SolicitudInsumo.objects.filter(
            clase__asignatura__profesor=profesor,
            estado="pendiente",
            es_extra=False  # Excluir solicitudes extraordinarias
        )


        # Serializar las solicitudes
        data = [
            {
                "id": solicitud.id,
                "alumno": solicitud.alumno.nombre,
                "insumo": solicitud.insumo.nombre,
                "cantidad_solicitada": solicitud.cantidad_solicitada,
                "unidad_medida": solicitud.insumo.get_unidad_medida_display(),
            }
            for solicitud in solicitudes
        ]

        return Response(data, status=status.HTTP_200_OK)


    @action(detail=False, methods=['get'], url_path='solicitudes_administrador', permission_classes=[IsAdmin])
    def solicitudes_administrador(self, request):
        """
        Devuelve las solicitudes que han sido aprobadas por el profesor y están pendientes de ser gestionadas por el administrador.
        """
        solicitudes = SolicitudInsumo.objects.filter(
            estado="pendiente_admin"  # Filtrar solo solicitudes que están pendientes del administrador
        )
        data = [
            {
                "id": solicitud.id,
                "alumno_nombre": solicitud.alumno.nombre,
                "insumo": solicitud.insumo.nombre,
                "unidad_medida": solicitud.insumo.get_unidad_medida_display(),
                "cantidad_solicitada": solicitud.cantidad_solicitada,
                "clase": solicitud.clase.id,  # Incluimos el ID de la clase para futuras acciones
            }
            for solicitud in solicitudes
        ]
        return Response(data, status=status.HTTP_200_OK)


    @action(detail=False, methods=['get'], url_path='historial_solicitudes', permission_classes=[AllowAny])
    def historial_solicitudes(self, request):
        """
        Historial de todas las solicitudes de insumos.
        """
        solicitudes = SolicitudInsumo.objects.select_related('alumno', 'clase', 'clase__asignatura', 'insumo').order_by('-creado_en')
        data = [
            {
                "alumno": solicitud.alumno.nombre,
                "insumo": solicitud.insumo.nombre,
                "cantidad_solicitada": solicitud.cantidad_solicitada,
                "cantidad_aprobada": solicitud.cantidad_aprobada,
                "estado": solicitud.estado,
                "fecha": solicitud.creado_en.strftime("%Y-%m-%d %H:%M:%S"),
                "clase": solicitud.clase.nombre,
                "asignatura": solicitud.clase.asignatura.nombre
            }
            for solicitud in solicitudes
        ]
        return Response({"solicitudes": data}, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'], url_path='historial_alumno', permission_classes=[IsAuthenticated])
    def historial_solicitudes_alumno(self, request):
        """
        Devuelve el historial de solicitudes realizadas por el alumno autenticado.
        """
        alumno = request.user

        # Verificar que el usuario sea un alumno
        if alumno.rol != "3":
            return Response(
                {"error": "Solo los alumnos pueden acceder a su historial de solicitudes."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Filtrar solicitudes realizadas por el alumno autenticado
        solicitudes = SolicitudInsumo.objects.filter(alumno=alumno).select_related("insumo", "clase").order_by("-creado_en")

        # Serializar las solicitudes
        data = [
            {
                "id": solicitud.id,
                "insumo": solicitud.insumo.nombre,
                "clase": solicitud.clase.nombre,
                "cantidad_solicitada": solicitud.cantidad_solicitada,
                "estado": solicitud.estado,
                "motivo_rechazo": solicitud.motivo_rechazo or "Sin motivo de rechazo especificado",
                "fecha_solicitud": solicitud.creado_en.strftime("%Y-%m-%d %H:%M:%S"),
            }
            for solicitud in solicitudes
        ]

        return Response(data, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'], url_path='historial_profesor', permission_classes=[IsAuthenticated])
    def historial_profesor(self, request):
        """
        Devuelve el historial de solicitudes gestionadas por el profesor autenticado.
        """
        profesor = request.user

        # Validar que el usuario sea un profesor
        if profesor.rol != "2":  # Asegúrate de que "2" es el rol de profesor
            return Response(
                {"error": "Solo los profesores pueden acceder a su historial de solicitudes."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Filtrar solicitudes gestionadas por este profesor
        solicitudes = SolicitudInsumo.objects.filter(
            clase__asignatura__profesor=profesor
        ).select_related('insumo', 'clase', 'alumno')

        # Serializar las solicitudes
        data = [
            {
                "id": solicitud.id,
                "alumno": solicitud.alumno.nombre,
                "insumo": solicitud.insumo.nombre,
                "clase": solicitud.clase.nombre,
                "cantidad_solicitada": solicitud.cantidad_solicitada,
                "estado": solicitud.estado,
                "motivo_rechazo": solicitud.motivo_rechazo,
                "fecha_solicitud": solicitud.creado_en.strftime("%Y-%m-%d %H:%M:%S"),
            }
            for solicitud in solicitudes
        ]

        return Response(data, status=status.HTTP_200_OK)



class NotificacionViewSet(viewsets.ModelViewSet):
    queryset = Notificacion.objects.all()
    serializer_class = NotificacionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Filtra las notificaciones para que cada usuario solo vea las suyas.
        """
        return Notificacion.objects.filter(usuario=self.request.user)

    @action(detail=True, methods=['post'], url_path='marcar_leida', permission_classes=[IsAuthenticated])
    def marcar_leida(self, request, pk=None):
        """
        Marca una notificación como leída.
        """
        try:
            # Obtener la notificación asegurando que pertenece al usuario autenticado
            notificacion = self.get_object()

            if notificacion.usuario != request.user:
                return Response(
                    {"error": "No tienes permiso para modificar esta notificación."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Marcar como leída
            notificacion.leida = True
            notificacion.save()

            return Response(
                {
                    "status": "Notificación marcada como leída.",
                    "notificacion_id": notificacion.id,
                    "leida": notificacion.leida,
                },
                status=status.HTTP_200_OK,
            )
        except Notificacion.DoesNotExist:
            return Response(
                {"error": "Notificación no encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=False, methods=['get'], url_path='alumno', permission_classes=[IsAuthenticated])
    def alumno(self, request):
        """
        Devuelve las notificaciones del usuario autenticado.
        """
        usuario = request.user
        notificaciones = Notificacion.objects.filter(usuario=usuario)
        serializer = self.get_serializer(notificaciones, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['delete'], url_path='eliminar', permission_classes=[IsAuthenticated])
    def eliminar(self, request, pk=None):
        """
        Permite al usuario eliminar una notificación.
        """
        try:
            # Obtener la notificación asegurando que pertenece al usuario autenticado
            notificacion = self.get_object()

            if notificacion.usuario != request.user:
                return Response(
                    {"error": "No tienes permiso para eliminar esta notificación."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Eliminar la notificación
            notificacion.delete()

            return Response(
                {"status": "Notificación eliminada correctamente."},
                status=status.HTTP_200_OK,
            )
        except Notificacion.DoesNotExist:
            return Response(
                {"error": "Notificación no encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )