"""
Modelo de usuario personalizado para TorneoX.

Se define un único modelo Usuario (extendiendo AbstractUser) con un campo
`rol` que distingue entre Administrador y Dirigente de equipo. Esto evita
crear perfiles separados y permite usar directamente el sistema de
autenticación y permisos nativo de Django.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    class Rol(models.TextChoices):
        ADMINISTRADOR = "ADMIN", "Administrador"
        DIRIGENTE = "DIRIGENTE", "Dirigente de equipo"

    rol = models.CharField(
        max_length=20,
        choices=Rol.choices,
        default=Rol.DIRIGENTE,
        verbose_name="Rol",
        help_text="Define qué puede ver y hacer el usuario dentro del sistema.",
    )
    telefono = models.CharField(max_length=20, blank=True, verbose_name="Teléfono")

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_rol_display()})"

    @property
    def es_administrador(self):
        return self.rol == self.Rol.ADMINISTRADOR

    @property
    def es_dirigente(self):
        return self.rol == self.Rol.DIRIGENTE
