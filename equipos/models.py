import hashlib
import re
import unicodedata

from django.core.exceptions import ValidationError
from django.db import models


def validar_cedula_ecuatoriana(valor):
    if not re.fullmatch(r"[0-9]{10}", valor):
        raise ValidationError("La cédula debe tener exactamente 10 dígitos.")

    provincia = int(valor[:2])
    if not 1 <= provincia <= 24 or int(valor[2]) > 5:
        raise ValidationError("La cédula ecuatoriana no tiene una estructura válida.")

    suma = 0
    for posicion, digito in enumerate(valor[:9]):
        producto = int(digito) * (2 if posicion % 2 == 0 else 1)
        suma += producto - 9 if producto > 9 else producto

    digito_verificador = (10 - suma % 10) % 10
    if digito_verificador != int(valor[9]):
        raise ValidationError("La cédula ecuatoriana no es válida.")


def normalizar_nombre_completo(nombres, apellidos):
    nombre_completo = f"{nombres} {apellidos}"
    sin_acentos = "".join(
        caracter
        for caracter in unicodedata.normalize("NFKD", nombre_completo)
        if not unicodedata.combining(caracter)
    )
    nombre_normalizado = " ".join(sin_acentos.casefold().split())
    return hashlib.sha256(nombre_normalizado.encode("utf-8")).hexdigest()


class Equipo(models.Model):
    torneo = models.ForeignKey(
        "torneos.Torneo",
        on_delete=models.CASCADE,
        related_name="equipos",
        verbose_name="Torneo",
    )
    nombre = models.CharField(max_length=120, verbose_name="Nombre del equipo")
    es_ficticio = models.BooleanField(
        default=False,
        verbose_name="Equipo ficticio",
        help_text="Marcador temporal para completar la cantidad par de participantes.",
    )
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="Registrado")

    class Meta:
        ordering = ["nombre"]
        verbose_name = "Equipo"
        verbose_name_plural = "Equipos"
        constraints = [
            models.UniqueConstraint(
                fields=["torneo", "nombre"],
                name="equipo_nombre_unico_por_torneo",
            ),
        ]

    def __str__(self):
        return f"{self.nombre} - {self.torneo.nombre}"


class Jugador(models.Model):
    equipo = models.ForeignKey(
        Equipo,
        on_delete=models.CASCADE,
        related_name="jugadores",
        verbose_name="Equipo",
    )
    cedula = models.CharField(
        max_length=10,
        unique=True,
        validators=[validar_cedula_ecuatoriana],
        verbose_name="Cédula",
    )
    nombres = models.CharField(max_length=150, verbose_name="Nombres")
    apellidos = models.CharField(max_length=150, verbose_name="Apellidos")
    nombre_completo_key = models.CharField(
        max_length=64,
        unique=True,
        editable=False,
    )
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="Registrado")

    class Meta:
        ordering = ["apellidos", "nombres"]
        verbose_name = "Jugador"
        verbose_name_plural = "Jugadores"

    def save(self, *args, **kwargs):
        self.nombre_completo_key = normalizar_nombre_completo(
            self.nombres,
            self.apellidos,
        )
        super().save(*args, **kwargs)

    @property
    def nombre_completo(self):
        return f"{self.nombres} {self.apellidos}"

    def __str__(self):
        return self.nombre_completo


class DirigenteEquipo(models.Model):
    equipo = models.ForeignKey(
        Equipo,
        on_delete=models.CASCADE,
        related_name="dirigentes",
        verbose_name="Equipo",
    )
    nombre = models.CharField(max_length=150, verbose_name="Nombre del dirigente")
    telefono = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="Teléfono",
    )
    correo_electronico = models.EmailField(
        blank=True,
        verbose_name="Correo electrónico",
    )
    es_prioritario = models.BooleanField(
        default=False,
        verbose_name="Dirigente prioritario",
        help_text="Es el contacto principal del equipo para el sistema.",
    )

    class Meta:
        ordering = ["-es_prioritario", "id"]
        verbose_name = "Dirigente de equipo"
        verbose_name_plural = "Dirigentes de equipo"
        constraints = [
            models.UniqueConstraint(
                fields=["equipo"],
                condition=models.Q(es_prioritario=True),
                name="un_dirigente_prioritario_por_equipo",
            ),
        ]

    def __str__(self):
        return self.nombre
