import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Torneo",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("nombre", models.CharField(max_length=120, verbose_name="Nombre del torneo")),
                (
                    "equipos_clasificados",
                    models.PositiveSmallIntegerField(
                        help_text="Cantidad de equipos que avanzarán desde la primera fase.",
                        validators=[django.core.validators.MinValueValidator(1)],
                        verbose_name="Equipos que clasifican",
                    ),
                ),
                (
                    "bonificacion_habilitada",
                    models.BooleanField(
                        default=False,
                        help_text="Al cerrar la fase, el primer y segundo lugar reciben puntos adicionales.",
                        verbose_name="Habilitar bonificación por posiciones",
                    ),
                ),
                ("creado_en", models.DateTimeField(auto_now_add=True, verbose_name="Creado")),
                ("actualizado_en", models.DateTimeField(auto_now=True, verbose_name="Última actualización")),
            ],
            options={
                "verbose_name": "Torneo",
                "verbose_name_plural": "Torneos",
                "ordering": ["-creado_en", "nombre"],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(equipos_clasificados__gte=1),
                        name="torneo_clasificados_mayor_que_cero",
                    ),
                ],
            },
        ),
    ]
