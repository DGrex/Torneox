from django.urls import include, path

from . import views

app_name = "torneos"

urlpatterns = [
    path("", views.lista_torneos, name="lista"),
    path("<int:pk>/editar/", views.editar_torneo, name="editar"),
    path("<int:pk>/eliminar/", views.eliminar_torneo, name="eliminar"),
    path("<int:pk>/", views.gestionar_torneo, name="gestionar"),
    path(
        "<int:pk>/calendario/generar/",
        views.generar_calendario,
        name="generar_calendario",
    ),
    path(
        "<int:pk>/calendario/reemplazar-por-historico/",
        views.reemplazar_calendario_por_jornadas_historicas,
        name="reemplazar_calendario_por_historicas",
    ),
    path(
        "<int:pk>/calendario/jornada-anterior/",
        views.registrar_jornada_anterior,
        name="registrar_jornada_anterior",
    ),
    path(
        "<int:pk>/jornadas/<int:jornada_id>/fecha/",
        views.actualizar_fecha_jornada,
        name="actualizar_fecha_jornada",
    ),
    path(
        "<int:pk>/encuentros/<int:encuentro_id>/resultado/",
        views.actualizar_resultado,
        name="actualizar_resultado",
    ),
    path(
        "<int:pk>/jornadas/<int:jornada_id>/orden/",
        views.reordenar_encuentros,
        name="reordenar_encuentros",
    ),
    path(
        "<int:torneo_id>/equipos/",
        include(("equipos.urls", "equipos"), namespace="equipos"),
    ),
]
