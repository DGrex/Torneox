from django.contrib import admin

from .models import Torneo


@admin.register(Torneo)
class TorneoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "equipos_clasificados", "bonificacion_habilitada", "actualizado_en")
    search_fields = ("nombre",)
    list_filter = ("bonificacion_habilitada",)
