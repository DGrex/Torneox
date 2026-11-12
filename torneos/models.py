from django.core.validators import MinValueValidator
from django.db import models


class Torneo(models.Model):
    FORMATO_FASE_INICIAL = "TODOS_CONTRA_TODOS"
    BONIFICACION_PRIMER_LUGAR = 2
    BONIFICACION_SEGUNDO_LUGAR = 1

    nombre = models.CharField(max_length=120, verbose_name="Nombre del torneo")
    equipos_participantes = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1)],
        verbose_name="Equipos que participarán",
        help_text="Opcional por ahora. Recuerda definirlo antes de iniciar el campeonato.",
    )
    equipos_clasificados = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1)],
        verbose_name="Equipos que clasifican",
        help_text="Opcional por ahora. Recuerda definirlo antes de cerrar la primera fase.",
    )
    jugadores_maximos_por_equipo = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1)],
        verbose_name="Máximo de jugadores por equipo",
        help_text="Recuerda definirlo antes de comenzar a registrar jugadores.",
    )
    bonificacion_habilitada = models.BooleanField(
        default=False,
        verbose_name="Habilitar bonificación por posiciones",
        help_text="Al cerrar la fase, el primer y segundo lugar reciben puntos adicionales.",
    )
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
    actualizado_en = models.DateTimeField(auto_now=True, verbose_name="Última actualización")

    class Meta:
        ordering = ["-creado_en", "nombre"]
        verbose_name = "Torneo"
        verbose_name_plural = "Torneos"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(equipos_clasificados__gte=1),
                name="torneo_clasificados_mayor_que_cero",
            ),
        ]

    def __str__(self):
        return self.nombre


class Jornada(models.Model):
    torneo = models.ForeignKey(
        Torneo,
        on_delete=models.CASCADE,
        related_name="jornadas",
        verbose_name="Torneo",
    )
    numero = models.PositiveSmallIntegerField(verbose_name="Número de jornada")
    fecha_programada = models.DateField(
        blank=True,
        null=True,
        verbose_name="Fecha programada",
    )
    equipo_libre = models.ForeignKey(
        "equipos.Equipo",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="jornadas_libres",
        verbose_name="Equipo libre",
    )

    class Meta:
        ordering = ["numero"]
        verbose_name = "Jornada"
        verbose_name_plural = "Jornadas"
        constraints = [
            models.UniqueConstraint(
                fields=["torneo", "numero"],
                name="jornada_numero_unico_por_torneo",
            ),
        ]

    def __str__(self):
        return f"{self.torneo.nombre} - Jornada {self.numero}"


class Encuentro(models.Model):
    jornada = models.ForeignKey(
        Jornada,
        on_delete=models.CASCADE,
        related_name="encuentros",
        verbose_name="Jornada",
    )
    equipo_local = models.ForeignKey(
        "equipos.Equipo",
        on_delete=models.PROTECT,
        related_name="encuentros_como_local",
        verbose_name="Equipo local",
    )
    equipo_visitante = models.ForeignKey(
        "equipos.Equipo",
        on_delete=models.PROTECT,
        related_name="encuentros_como_visitante",
        verbose_name="Equipo visitante",
    )
    orden = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Orden en la jornada",
    )
    goles_local = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        verbose_name="Goles del local",
    )
    goles_visitante = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        verbose_name="Goles del visitante",
    )

    class Meta:
        ordering = ["orden", "id"]
        verbose_name = "Encuentro"
        verbose_name_plural = "Encuentros"
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(equipo_local=models.F("equipo_visitante")),
                name="encuentro_equipos_distintos",
            ),
            models.UniqueConstraint(
                fields=["jornada", "equipo_local"],
                name="encuentro_local_unico_por_jornada",
            ),
            models.UniqueConstraint(
                fields=["jornada", "equipo_visitante"],
                name="encuentro_visitante_unico_por_jornada",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(goles_local__isnull=True, goles_visitante__isnull=True)
                    | models.Q(goles_local__isnull=False, goles_visitante__isnull=False)
                ),
                name="encuentro_resultado_completo_o_vacio",
            ),
        ]

    @property
    def jugado(self):
        return self.goles_local is not None and self.goles_visitante is not None

    def __str__(self):
        return f"{self.equipo_local} vs {self.equipo_visitante}"
