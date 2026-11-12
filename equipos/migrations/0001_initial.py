from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("torneos", "0002_torneo_equipos_participantes"),
    ]

    operations = [
        migrations.CreateModel(
            name="Equipo",
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
                ("nombre", models.CharField(max_length=120, verbose_name="Nombre del equipo")),
                ("creado_en", models.DateTimeField(auto_now_add=True, verbose_name="Registrado")),
                (
                    "torneo",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="equipos",
                        to="torneos.torneo",
                        verbose_name="Torneo",
                    ),
                ),
            ],
            options={
                "verbose_name": "Equipo",
                "verbose_name_plural": "Equipos",
                "ordering": ["nombre"],
            },
        ),
        migrations.CreateModel(
            name="DirigenteEquipo",
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
                ("nombre", models.CharField(max_length=150, verbose_name="Nombre del dirigente")),
                (
                    "es_prioritario",
                    models.BooleanField(
                        default=False,
                        help_text="Es el contacto principal del equipo para el sistema.",
                        verbose_name="Dirigente prioritario",
                    ),
                ),
                (
                    "equipo",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dirigentes",
                        to="equipos.equipo",
                        verbose_name="Equipo",
                    ),
                ),
            ],
            options={
                "verbose_name": "Dirigente de equipo",
                "verbose_name_plural": "Dirigentes de equipo",
                "ordering": ["-es_prioritario", "id"],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("es_prioritario", True)),
                        fields=("equipo",),
                        name="un_dirigente_prioritario_por_equipo",
                    ),
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="equipo",
            constraint=models.UniqueConstraint(
                fields=("torneo", "nombre"),
                name="equipo_nombre_unico_por_torneo",
            ),
        ),
    ]
