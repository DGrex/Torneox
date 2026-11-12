import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("torneos", "0002_torneo_equipos_participantes"),
    ]

    operations = [
        migrations.AddField(
            model_name="torneo",
            name="jugadores_maximos_por_equipo",
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text="Recuerda definirlo antes de comenzar a registrar jugadores.",
                null=True,
                validators=[django.core.validators.MinValueValidator(1)],
                verbose_name="Máximo de jugadores por equipo",
            ),
        ),
    ]
