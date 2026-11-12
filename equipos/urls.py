from django.urls import path

from . import views

app_name = "equipos"

urlpatterns = [
    path("", views.lista_equipos, name="lista"),
    path(
        "agregar-ficticio/",
        views.agregar_equipo_ficticio,
        name="agregar_ficticio",
    ),
    path(
        "<int:equipo_id>/reemplazar-ficticio/",
        views.reemplazar_equipo_ficticio,
        name="reemplazar_ficticio",
    ),
    path(
        "<int:equipo_id>/editar/",
        views.editar_equipo,
        name="editar",
    ),
    path(
        "<int:equipo_id>/eliminar/",
        views.eliminar_equipo,
        name="eliminar",
    ),
    path(
        "<int:equipo_id>/jugadores/",
        views.lista_jugadores,
        name="jugadores",
    ),
    path(
        "<int:equipo_id>/jugadores/<int:jugador_id>/editar/",
        views.editar_jugador,
        name="editar_jugador",
    ),
    path(
        "<int:equipo_id>/jugadores/<int:jugador_id>/eliminar/",
        views.eliminar_jugador,
        name="eliminar_jugador",
    ),
]
