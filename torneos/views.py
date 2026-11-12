from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Case, Count, IntegerField, Prefetch, Q, Value, When
from django.forms import DateField
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import (
    FechaJornadaForm,
    ResultadoEncuentroForm,
    TorneoForm,
    jornada_historica_formset,
)
from .models import Encuentro, Jornada, Torneo
from .services import (
    crear_calendario_todos_contra_todos,
    registrar_jornada_historica,
)


def _require_administrator(user):
    if not (user.is_superuser or user.es_administrador):
        raise PermissionDenied


def _calendario_puede_reiniciarse(torneo):
    cantidad_equipos = torneo.equipos.count()
    cantidad_partidos = cantidad_equipos * (cantidad_equipos - 1) // 2
    partidos = list(
        Encuentro.objects.filter(jornada__torneo=torneo).values_list(
            "equipo_local_id",
            "equipo_visitante_id",
            "goles_local",
            "goles_visitante",
        )
    )
    parejas = {
        frozenset((equipo_local_id, equipo_visitante_id))
        for equipo_local_id, equipo_visitante_id, _, _ in partidos
    }
    return (
        cantidad_partidos > 0
        and len(partidos) == cantidad_partidos
        and len(parejas) == cantidad_partidos
        and not any(goles_local is not None for _, _, goles_local, _ in partidos)
        and not torneo.jornadas.filter(fecha_programada__isnull=False).exists()
    )


@login_required
def lista_torneos(request):
    _require_administrator(request.user)
    form = TorneoForm(request.POST if request.method == "POST" else None)

    if request.method == "POST" and form.is_valid():
        torneo = form.save()
        messages.success(request, f"El torneo «{torneo.nombre}» fue creado.")
        return redirect("torneos:lista")

    return render(
        request,
        "torneos/panel.html",
        {
            "form": form,
            "torneos": Torneo.objects.all(),
            "bonificacion_primer_lugar": Torneo.BONIFICACION_PRIMER_LUGAR,
            "bonificacion_segundo_lugar": Torneo.BONIFICACION_SEGUNDO_LUGAR,
        },
    )


@login_required
def editar_torneo(request, pk):
    _require_administrator(request.user)
    torneo = get_object_or_404(Torneo, pk=pk)
    form = TorneoForm(
        request.POST if request.method == "POST" else None,
        instance=torneo,
    )

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Se actualizaron las reglas de «{torneo.nombre}».")
        return redirect("torneos:lista")

    return render(
        request,
        "torneos/formulario.html",
        {
            "form": form,
            "torneo": torneo,
            "bonificacion_primer_lugar": Torneo.BONIFICACION_PRIMER_LUGAR,
            "bonificacion_segundo_lugar": Torneo.BONIFICACION_SEGUNDO_LUGAR,
        },
    )


@login_required
def eliminar_torneo(request, pk):
    _require_administrator(request.user)
    torneo = get_object_or_404(Torneo, pk=pk)

    if request.method == "POST":
        nombre = torneo.nombre
        with transaction.atomic():
            Encuentro.objects.filter(jornada__torneo=torneo).delete()
            torneo.delete()
        messages.success(
            request,
            f"Se eliminó el torneo «{nombre}» y todos sus equipos, jugadores y jornadas.",
        )
        return redirect("torneos:lista")

    return render(
        request,
        "confirmar_eliminacion.html",
        {
            "titulo": "Eliminar torneo",
            "elemento": torneo.nombre,
            "aviso": (
                "Se eliminarán también sus equipos, jugadores, dirigentes, "
                "jornadas, partidos y resultados. Esta acción no se puede deshacer."
            ),
            "url_cancelar": reverse("torneos:lista"),
            "texto_confirmar": "Eliminar torneo y todos sus datos",
        },
    )


@login_required
def gestionar_torneo(request, pk):
    _require_administrator(request.user)
    torneo = get_object_or_404(Torneo, pk=pk)
    equipos = torneo.equipos.prefetch_related("jugadores", "dirigentes")
    jornadas = (
        torneo.jornadas.select_related("equipo_libre")
        .annotate(
            total_partidos=Count("encuentros"),
            partidos_jugados=Count(
                "encuentros",
                filter=Q(encuentros__goles_local__isnull=False),
            ),
        )
        .prefetch_related(
            Prefetch(
                "encuentros",
                queryset=Encuentro.objects.select_related(
                    "equipo_local",
                    "equipo_visitante",
                )
                .annotate(
                    partido_ficticio=Case(
                        When(
                            Q(equipo_local__es_ficticio=True)
                            | Q(equipo_visitante__es_ficticio=True),
                            then=Value(1),
                        ),
                        default=Value(0),
                        output_field=IntegerField(),
                    )
                )
                .order_by("partido_ficticio", "orden", "pk"),
            ),
        )
    )
    partidos = list(
        Encuentro.objects.filter(jornada__torneo=torneo).values_list(
            "equipo_local_id",
            "equipo_visitante_id",
        )
    )
    partidos_total = len(partidos)
    cantidad_equipos = equipos.count()
    partidos_esperados = cantidad_equipos * (cantidad_equipos - 1) // 2
    parejas_registradas = {
        frozenset((equipo_local_id, equipo_visitante_id))
        for equipo_local_id, equipo_visitante_id in partidos
    }
    calendario_generado = (
        partidos_esperados > 0
        and partidos_total == partidos_esperados
        and len(parejas_registradas) == partidos_esperados
    )
    formset_jornada = jornada_historica_formset(torneo)

    return render(
        request,
        "torneos/gestionar.html",
        {
            "torneo": torneo,
            "equipos": equipos,
            "jornadas": jornadas,
            "calendario_generado": calendario_generado,
            "formset_jornada_historica": formset_jornada,
            "partidos_total": partidos_total,
            "faltan_equipos": (
                torneo.equipos_participantes is not None
                and equipos.count() < torneo.equipos_participantes
            ),
            "calendario_reiniciable": _calendario_puede_reiniciarse(torneo),
        },
    )


@login_required
def reemplazar_calendario_por_jornadas_historicas(request, pk):
    _require_administrator(request.user)
    torneo = get_object_or_404(Torneo, pk=pk)

    if request.method == "POST":
        with transaction.atomic():
            torneo = Torneo.objects.select_for_update().get(pk=pk)
            if not _calendario_puede_reiniciarse(torneo):
                messages.error(
                    request,
                    "Solo se puede reemplazar un calendario completo que no tenga "
                    "fechas programadas ni resultados.",
                )
                return redirect("torneos:gestionar", pk=pk)

            torneo.jornadas.all().delete()
        messages.success(
            request,
            "Se quitó el calendario pendiente. Los equipos se conservaron; ahora "
            "puedes registrar las jornadas históricas con sus cruces.",
        )
        return redirect("torneos:gestionar", pk=pk)

    if not _calendario_puede_reiniciarse(torneo):
        messages.error(
            request,
            "Este calendario no se puede reemplazar porque tiene fechas o "
            "resultados registrados.",
        )
        return redirect("torneos:gestionar", pk=pk)

    return render(
        request,
        "confirmar_eliminacion.html",
        {
            "titulo": "Reemplazar calendario pendiente",
            "elemento": f"Calendario de «{torneo.nombre}»",
            "aviso": (
                "Se eliminarán únicamente las jornadas y partidos generados que "
                "aún no tienen fecha ni resultado. Los equipos no se modificarán. "
                "Después podrás ingresar cada jornada ya jugada con sus cruces y "
                "agregar los marcadores más tarde."
            ),
            "url_cancelar": reverse("torneos:gestionar", args=[pk]),
            "texto_confirmar": "Reemplazar calendario pendiente",
        },
    )


@login_required
@require_POST
def registrar_jornada_anterior(request, pk):
    _require_administrator(request.user)
    torneo = get_object_or_404(Torneo, pk=pk)
    formset = jornada_historica_formset(torneo, request.POST)

    try:
        fecha = DateField().clean(request.POST.get("fecha_programada"))
    except ValidationError:
        fecha = None

    if not formset.is_valid() or not fecha:
        messages.error(request, "Completa la fecha y todos los cruces de la jornada.")
        return redirect("torneos:gestionar", pk=pk)

    partidos = [form.cleaned_data for form in formset.forms]
    try:
        jornada = registrar_jornada_historica(
            torneo,
            fecha,
            partidos,
        )
    except (IntegrityError, ValidationError) as error:
        messages.error(request, str(error))
    else:
        messages.success(
            request,
            f"Se guardó la jornada {jornada.numero} con "
            f"{len(partidos)} partidos. Puedes registrar los resultados después.",
        )
    return redirect("torneos:gestionar", pk=pk)


@login_required
@require_POST
def actualizar_fecha_jornada(request, pk, jornada_id):
    _require_administrator(request.user)
    jornada = get_object_or_404(Jornada, pk=jornada_id, torneo_id=pk)
    form = FechaJornadaForm(request.POST, instance=jornada)

    if form.is_valid():
        form.save()
        messages.success(request, f"Se actualizó la fecha de la jornada {jornada.numero}.")
    else:
        messages.error(request, "No se pudo actualizar la fecha programada.")

    return redirect("torneos:gestionar", pk=pk)


@login_required
@require_POST
def actualizar_resultado(request, pk, encuentro_id):
    _require_administrator(request.user)
    encuentro = get_object_or_404(
        Encuentro.objects.select_related("jornada"),
        pk=encuentro_id,
        jornada__torneo_id=pk,
    )
    form = ResultadoEncuentroForm(request.POST, instance=encuentro)

    if form.is_valid():
        form.save()
        messages.success(request, "Se guardó el resultado del partido.")
    else:
        messages.error(request, "Ingresa un marcador válido para ambos equipos.")

    return redirect("torneos:gestionar", pk=pk)


@login_required
@require_POST
def reordenar_encuentros(request, pk, jornada_id):
    _require_administrator(request.user)
    jornada = get_object_or_404(Jornada, pk=jornada_id, torneo_id=pk)
    ids_enviados = request.POST.get("orden_ids", "").split(",")

    try:
        ids_ordenados = [int(encuentro_id) for encuentro_id in ids_enviados]
    except ValueError:
        messages.error(request, "El orden enviado no es válido.")
        return redirect("torneos:gestionar", pk=pk)

    encuentros = list(jornada.encuentros.all())
    ids_actuales = {encuentro.pk for encuentro in encuentros}
    if (
        len(ids_ordenados) != len(ids_actuales)
        or len(set(ids_ordenados)) != len(ids_ordenados)
        or set(ids_ordenados) != ids_actuales
    ):
        messages.error(
            request,
            "No se guardó el orden: debe incluir cada partido de esta jornada una sola vez.",
        )
        return redirect("torneos:gestionar", pk=pk)

    ids_ficticios = {
        encuentro.pk
        for encuentro in encuentros
        if encuentro.equipo_local.es_ficticio or encuentro.equipo_visitante.es_ficticio
    }
    if ids_ficticios and (
        len(ids_ficticios) != 1
        or ids_ordenados[-1] != next(iter(ids_ficticios))
    ):
        messages.error(
            request,
            "El partido del equipo ficticio debe permanecer al final de la jornada.",
        )
        return redirect("torneos:gestionar", pk=pk)

    encuentros_por_id = {encuentro.pk: encuentro for encuentro in encuentros}
    for orden, encuentro_id in enumerate(ids_ordenados):
        encuentros_por_id[encuentro_id].orden = orden
    Encuentro.objects.bulk_update(encuentros, ["orden"])
    messages.success(request, f"Se guardó el orden de los partidos de la jornada {jornada.numero}.")
    return redirect("torneos:gestionar", pk=pk)


@login_required
@require_POST
def generar_calendario(request, pk):
    _require_administrator(request.user)
    try:
        with transaction.atomic():
            torneo = Torneo.objects.select_for_update().get(pk=pk)
            jornadas_creadas = crear_calendario_todos_contra_todos(torneo)
    except Torneo.DoesNotExist:
        get_object_or_404(Torneo, pk=pk)
    except (ValueError, IntegrityError) as error:
        messages.error(request, str(error))
    else:
        mensajes = (
            f"Calendario generado: {jornadas_creadas} jornadas y "
            f"{Encuentro.objects.filter(jornada__torneo=torneo).count()} partidos."
        )
        if torneo.equipos_participantes and torneo.equipos.count() < torneo.equipos_participantes:
            mensajes += (
                f" El calendario incluye los {torneo.equipos.count()} equipos registrados; "
                f"faltan {torneo.equipos_participantes - torneo.equipos.count()} "
                "para completar el cupo configurado."
            )
        messages.success(request, mensajes)

    return redirect("torneos:gestionar", pk=pk)
