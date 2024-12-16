from rest_framework import serializers
from .models import Usuario
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

class UsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = ['id', 'nombre', 'email', 'password', 'rol']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        usuario = Usuario(**validated_data)
        if password is not None:
            usuario.set_password(password)
        usuario.save()
        return usuario


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        
        # Agregar el rol del usuario al payload del token
        token["nombre"] = user.nombre  # Asegúrate de que el campo existe en tu modelo Usuario
        token["email"] = user.email  # Asegúrate de que el campo existe en tu modelo Usuario
        token['rol'] = user.rol  # Asumiendo que el campo rol existe en tu modelo Usuario
        
        return token

