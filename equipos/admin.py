from django.contrib import admin

from .models import DirigenteEquipo, Equipo, Jugador


class DirigenteEquipoInline(admin.TabularInline):
    model = DirigenteEquipo
    extra = 0


class JugadorInline(admin.TabularInline):
    model = Jugador
    extra = 0


@admin.register(Equipo)
class EquipoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "torneo", "creado_en")
    list_filter = ("torneo",)
    search_fields = ("nombre", "dirigentes__nombre")
    inlines = [DirigenteEquipoInline, JugadorInline]


@admin.register(Jugador)
class JugadorAdmin(admin.ModelAdmin):
    list_display = ("nombre_completo", "cedula", "equipo")
    list_filter = ("equipo__torneo",)
    search_fields = ("cedula", "nombres", "apellidos", "equipo__nombre")
