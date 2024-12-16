from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario

class UsuarioAdmin(UserAdmin):
    list_display = ('email', 'nombre', 'rol', 'is_active', 'is_staff')
    list_filter = ('rol', 'is_staff', 'is_active')
    search_fields = ('email', 'nombre')
    ordering = ('email',)
    fieldsets = (
        (None, {'fields': ('email', 'nombre', 'password')}),
        ('Permissions', {'fields': ('rol', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'nombre', 'password1', 'password2', 'rol', 'is_staff', 'is_active')}
        ),
    )

admin.site.register(Usuario, UsuarioAdmin)
