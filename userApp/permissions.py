from rest_framework.permissions import BasePermission

class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        # Verifica si el usuario está autenticado y si tiene el rol de administrador (rol = "1")
        return request.user.is_authenticated and request.user.rol == "1"

class IsProfesor(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.rol == "2"

class IsEstudiante(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.rol == "3"

class IsProfesorOrAdmin(BasePermission):
    """
    Permiso para verificar si el usuario es profesor o administrador.
    """
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and 
            (request.user.rol == "2" or request.user.rol == "3")
        )
