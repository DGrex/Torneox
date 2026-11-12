import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("torneos", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="torneo",
            name="equipos_participantes",
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text="Opcional por ahora. Recuerda definirlo antes de iniciar el campeonato.",
                null=True,
                validators=[django.core.validators.MinValueValidator(1)],
                verbose_name="Equipos que participarán",
            ),
        ),
        migrations.AlterField(
            model_name="torneo",
            name="equipos_clasificados",
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text="Opcional por ahora. Recuerda definirlo antes de cerrar la primera fase.",
                null=True,
                validators=[django.core.validators.MinValueValidator(1)],
                verbose_name="Equipos que clasifican",
            ),
        ),
    ]
