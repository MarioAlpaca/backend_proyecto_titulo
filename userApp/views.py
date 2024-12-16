from rest_framework import generics, viewsets, status
from .models import Usuario
from .serializers import UsuarioSerializer
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import CustomTokenObtainPairSerializer
from .permissions import IsAdmin
from rest_framework.decorators import action
from django.contrib.auth.hashers import make_password


class UsuarioCreateView(generics.CreateAPIView):
    queryset = Usuario.objects.all()
    serializer_class = UsuarioSerializer
    permission_classes = [IsAuthenticated]

class UsuarioView(viewsets.ModelViewSet):
    serializer_class = UsuarioSerializer
    permission_classes = [IsAuthenticated] 

    def get_queryset(self):
        rol = self.request.query_params.get('rol')
        queryset = Usuario.objects.all()
        if rol:
            queryset = queryset.filter(rol=rol)
        return queryset
    
    @action(detail=False, methods=['post'], url_path='registrar', permission_classes=[IsAuthenticated])
    def registrar_usuario(self, request):
        """
        Permite al administrador registrar un nuevo usuario.
        """
        data = request.data
        if not data.get('password'):
            return Response({"error": "La contraseña es obligatoria"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Usuario registrado correctamente", "usuario": serializer.data}, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'], url_path='alumnos', permission_classes=[IsAuthenticated])
    def get_alumnos(self, request):
        """
        Devuelve todos los usuarios con el rol de alumno (rol 3).
        """
        alumnos = Usuario.objects.filter(rol=3)
        serializer = self.get_serializer(alumnos, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='listar_usuarios', permission_classes=[IsAdmin])
    def listar_usuarios(self, request):
        """
        Devuelve la lista de todos los usuarios registrados.
        """
        usuarios = Usuario.objects.all().order_by('id')
        serializer = self.get_serializer(usuarios, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['patch', 'put'], url_path='editar', permission_classes=[IsAdmin])
    def editar_usuario(self, request, pk=None):
        """
        Permite a un administrador editar el nombre y/o contraseña de un usuario.
        """
        try:
            usuario = Usuario.objects.get(pk=pk)
            data = request.data

            if "nombre" in data:
                usuario.nombre = data["nombre"]
            if "password" in data:
                usuario.password = make_password(data["password"])  # Encriptar la contraseña

            usuario.save()
            return Response({"status": "Usuario actualizado correctamente"}, status=status.HTTP_200_OK)
        except Usuario.DoesNotExist:
            return Response({"error": "Usuario no encontrado"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Error al actualizar usuario: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

class UsuarioPorRolView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        rol = request.query_params.get('rol')
        if rol is not None:
            usuarios = Usuario.objects.filter(rol=rol)
        else:
            usuarios = Usuario.objects.all()
        serializer = UsuarioSerializer(usuarios, many=True)
        return Response(serializer.data)