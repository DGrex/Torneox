from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from torneos.models import Encuentro, Torneo
from torneos.services import (
    adaptar_calendario_al_ingresar_equipo,
    crear_equipo_ficticio,
)

from .forms import (
    EquipoForm,
    JugadorForm,
    ReemplazarEquipoFicticioForm,
)
from .models import Equipo, Jugador


def _require_administrator(user):
    if not (user.is_superuser or user.es_administrador):
        raise PermissionDenied


@login_required
def lista_equipos(request, torneo_id):
    _require_administrator(request.user)
    torneo = get_object_or_404(Torneo, pk=torneo_id)
    equipos_actuales = Equipo.objects.filter(torneo=torneo).count()
    partidos_esperados = equipos_actuales * (equipos_actuales - 1) // 2
    calendario_generado = (
        partidos_esperados > 0
        and Encuentro.objects.filter(jornada__torneo=torneo).count()
        == partidos_esperados
    )
    form = EquipoForm(request.POST if request.method == "POST" else None)
    limite_alcanzado = False
    ficticio_pendiente = False
    historial_iniciado = False

    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                torneo = Torneo.objects.select_for_update().get(pk=torneo.pk)
                equipos_registrados = Equipo.objects.filter(torneo=torneo).count()
                ficticio_pendiente = Equipo.objects.filter(
                    torneo=torneo,
                    es_ficticio=True,
                ).exists()
                partidos_esperados = (
                    equipos_registrados * (equipos_registrados - 1) // 2
                )
                calendario_generado = (
                    partidos_esperados > 0
                    and Encuentro.objects.filter(jornada__torneo=torneo).count()
                    == partidos_esperados
                )
                historial_iniciado = (
                    not calendario_generado
                    and Encuentro.objects.filter(jornada__torneo=torneo).exists()
                )
                limite_alcanzado = (
                    torneo.equipos_participantes is not None
                    and equipos_registrados >= torneo.equipos_participantes
                )
                necesita_otro_ficticio = equipos_registrados % 2 == 0
                falta_cupo_para_pareja = (
                    torneo.equipos_participantes is not None
                    and equipos_registrados + 2 > torneo.equipos_participantes
                )
                if historial_iniciado:
                    pass
                elif ficticio_pendiente:
                    pass
                elif not limite_alcanzado and not (
                    necesita_otro_ficticio and falta_cupo_para_pareja
                ):
                    equipo = form.save(commit=False)
                    equipo.torneo = torneo
                    equipo.save()
                    form.guardar_dirigentes(equipo)
                    if necesita_otro_ficticio:
                        ficticio = crear_equipo_ficticio(torneo)
                        messages.info(
                            request,
                            f"Se agregó «{ficticio.nombre}» como equipo ficticio "
                            "para mantener la cantidad par.",
                        )
                    if calendario_generado:
                        adaptar_calendario_al_ingresar_equipo(torneo)
                elif necesita_otro_ficticio and falta_cupo_para_pareja:
                    limite_alcanzado = True
        except IntegrityError:
            form.add_error(
                "nombre",
                "No se pudo guardar el equipo. Verifica que el nombre no esté repetido.",
            )
        else:
            if historial_iniciado:
                form.add_error(
                    None,
                    "Ya hay jornadas históricas registradas. Completa primero "
                    "la inscripción de equipos para no alterar esas fechas.",
                )
            elif ficticio_pendiente:
                form.add_error(
                    None,
                    "Reemplaza el equipo ficticio existente por este equipo real "
                    "para conservar la cantidad par.",
                )
            elif limite_alcanzado:
                messages.error(
                    request,
                    "Se alcanzó el límite de participantes o no quedan cupos "
                    "suficientes para mantener una cantidad par. Revisa las reglas "
                    "del torneo.",
                )
            else:
                mensaje = f"El equipo «{equipo.nombre}» fue registrado."
                if calendario_generado:
                    mensaje += (
                        " Sus partidos pendientes ocuparon los espacios libres "
                        "disponibles en las jornadas; los encuentros y resultados "
                        "anteriores se conservaron."
                    )
                messages.success(request, mensaje)
                return redirect("torneos:equipos:lista", torneo_id=torneo.pk)

    equipos = Equipo.objects.filter(torneo=torneo).prefetch_related(
        "dirigentes",
        "jugadores",
    )
    equipo_ficticio = equipos.filter(es_ficticio=True).first()
    equipos_registrados = equipos.count()
    limite_alcanzado = limite_alcanzado or (
        torneo.equipos_participantes is not None
        and equipos_registrados >= torneo.equipos_participantes
    )

    return render(
        request,
        "equipos/lista.html",
        {
            "torneo": torneo,
            "equipos": equipos,
            "form": form,
            "limite_alcanzado": limite_alcanzado,
            "equipos_registrados": equipos_registrados,
            "calendario_generado": calendario_generado,
            "equipo_ficticio": equipo_ficticio,
        },
    )


@login_required
def agregar_equipo_ficticio(request, torneo_id):
    _require_administrator(request.user)
    if request.method != "POST":
        return redirect("torneos:equipos:lista", torneo_id=torneo_id)
    torneo = get_object_or_404(Torneo, pk=torneo_id)
    try:
        equipo = crear_equipo_ficticio(torneo)
    except ValidationError as error:
        messages.error(request, str(error))
    else:
        messages.success(
            request,
            f"Se agregó «{equipo.nombre}» para completar la cantidad par. "
            "Cuando llegue el equipo real, reemplaza este registro; se conservarán "
            "sus jornadas y partidos.",
        )
    return redirect("torneos:equipos:lista", torneo_id=torneo_id)


@login_required
def reemplazar_equipo_ficticio(request, torneo_id, equipo_id):
    _require_administrator(request.user)
    equipo = get_object_or_404(
        Equipo,
        pk=equipo_id,
        torneo_id=torneo_id,
        es_ficticio=True,
    )
    form = ReemplazarEquipoFicticioForm(
        request.POST if request.method == "POST" else None,
    )
    if request.method == "POST" and form.is_valid():
        equipo.nombre = form.cleaned_data["nombre"]
        equipo.es_ficticio = False
        try:
            equipo.save(update_fields=["nombre", "es_ficticio"])
        except IntegrityError:
            form.add_error("nombre", "Ya existe un equipo con ese nombre en el torneo.")
        else:
            messages.success(
                request,
                f"«{equipo.nombre}» reemplazó al equipo ficticio. "
                "Se conservaron los partidos y resultados existentes.",
            )
            return redirect("torneos:equipos:lista", torneo_id=torneo_id)
    return render(
        request,
        "equipos/reemplazar_ficticio.html",
        {"equipo": equipo, "torneo": equipo.torneo, "form": form},
    )


@login_required
def editar_equipo(request, torneo_id, equipo_id):
    _require_administrator(request.user)
    equipo = get_object_or_404(
        Equipo.objects.select_related("torneo").prefetch_related("dirigentes"),
        pk=equipo_id,
        torneo_id=torneo_id,
    )
    if equipo.es_ficticio:
        return redirect(
            "torneos:equipos:reemplazar_ficticio",
            torneo_id=torneo_id,
            equipo_id=equipo_id,
        )
    form = EquipoForm(
        request.POST if request.method == "POST" else None,
        instance=equipo,
    )

    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                equipo = form.save()
                form.guardar_dirigentes(equipo)
        except IntegrityError:
            form.add_error(
                "nombre",
                "No se pudo guardar. Verifica que el nombre del equipo no esté repetido en este torneo.",
            )
        else:
            messages.success(request, f"Se actualizaron los datos de «{equipo.nombre}».")
            return redirect("torneos:equipos:lista", torneo_id=torneo_id)

    return render(
        request,
        "equipos/editar_equipo.html",
        {"equipo": equipo, "torneo": equipo.torneo, "form": form},
    )


@login_required
def eliminar_equipo(request, torneo_id, equipo_id):
    _require_administrator(request.user)
    equipo = get_object_or_404(
        Equipo.objects.select_related("torneo"),
        pk=equipo_id,
        torneo_id=torneo_id,
    )
    encuentros_equipo = list(
        Encuentro.objects.filter(
            Q(equipo_local=equipo) | Q(equipo_visitante=equipo)
        ).select_related("jornada", "equipo_local", "equipo_visitante")
    )
    partidos_jugados = sum(
        1 for e in encuentros_equipo if e.goles_local is not None
    )

    if partidos_jugados:
        messages.error(
            request,
            "No se puede eliminar este equipo porque ya tiene partidos jugados "
            "con resultados registrados.",
        )
        return redirect("torneos:equipos:lista", torneo_id=torneo_id)

    equipos_count = Equipo.objects.filter(torneo_id=torneo_id).count()
    quedaria_impar = (equipos_count - 1) % 2 == 1

    if request.method == "POST":
        nombre = equipo.nombre
        torneo = equipo.torneo
        slots = [
            {
                "jornada": e.jornada,
                "otro": e.equipo_visitante if e.equipo_local_id == equipo.pk else e.equipo_local,
                "era_local": e.equipo_local_id == equipo.pk,
                "orden": e.orden,
            }
            for e in encuentros_equipo
        ]

        with transaction.atomic():
            Encuentro.objects.filter(
                Q(equipo_local=equipo) | Q(equipo_visitante=equipo)
            ).delete()
            equipo.delete()

            if quedaria_impar:
                base = "FICTICIO - Equipo pendiente"
                ficticio_nombre = base
                sufijo = 2
                while Equipo.objects.filter(torneo=torneo, nombre=ficticio_nombre).exists():
                    ficticio_nombre = f"{base} {sufijo}"
                    sufijo += 1
                ficticio = Equipo.objects.create(
                    torneo=torneo,
                    nombre=ficticio_nombre,
                    es_ficticio=True,
                )
                if slots:
                    Encuentro.objects.bulk_create([
                        Encuentro(
                            jornada=slot["jornada"],
                            equipo_local=ficticio if slot["era_local"] else slot["otro"],
                            equipo_visitante=slot["otro"] if slot["era_local"] else ficticio,
                            orden=slot["orden"],
                        )
                        for slot in slots
                    ])
                messages.success(
                    request,
                    f"Se eliminó el equipo «{nombre}» y sus partidos pendientes. "
                    f"Se creó el equipo ficticio «{ficticio_nombre}» para mantener la "
                    "cantidad par de equipos y se restablecieron sus partidos en el calendario.",
                )
            else:
                messages.success(
                    request,
                    f"Se eliminó el equipo «{nombre}», sus jugadores y sus partidos pendientes.",
                )
        return redirect("torneos:equipos:lista", torneo_id=torneo_id)

    return render(
        request,
        "confirmar_eliminacion.html",
        {
            "titulo": "Eliminar equipo",
            "elemento": equipo.nombre,
            "aviso": (
                "Se eliminarán también sus jugadores, dirigentes y partidos "
                "pendientes. Un equipo con resultados registrados no se puede eliminar."
                + (
                    " Al quedar una cantidad impar de equipos, se creará automáticamente "
                    "un equipo ficticio para conservar el calendario."
                    if quedaria_impar
                    else ""
                )
            ),
            "url_cancelar": reverse(
                "torneos:equipos:lista",
                args=[torneo_id],
            ),
            "texto_confirmar": "Eliminar equipo y sus datos",
        },
    )


@login_required
def lista_jugadores(request, torneo_id, equipo_id):
    _require_administrator(request.user)
    equipo = get_object_or_404(
        Equipo.objects.select_related("torneo"),
        pk=equipo_id,
        torneo_id=torneo_id,
    )
    jugadores = equipo.jugadores.all()
    jugadores_registrados = jugadores.count()
    limite_jugadores = equipo.torneo.jugadores_maximos_por_equipo
    limite_alcanzado = (
        limite_jugadores is not None
        and jugadores_registrados >= limite_jugadores
    )
    form = JugadorForm(
        request.POST
        if request.method == "POST" and "registrar_jugador" in request.POST
        else None
    )

    if request.method == "POST" and "registrar_jugador" in request.POST:
        if limite_alcanzado:
            form.add_error(
                None,
                f"Este equipo alcanzó el máximo de {limite_jugadores} jugadores.",
            )
        elif form.is_valid():
            try:
                with transaction.atomic():
                    equipo = Equipo.objects.select_for_update().select_related("torneo").get(
                        pk=equipo.pk,
                    )
                    jugadores_registrados = equipo.jugadores.count()
                    limite_jugadores = equipo.torneo.jugadores_maximos_por_equipo
                    if (
                        limite_jugadores is not None
                        and jugadores_registrados >= limite_jugadores
                    ):
                        limite_alcanzado = True
                    else:
                        jugador = form.save(commit=False)
                        jugador.equipo = equipo
                        jugador.save()
            except IntegrityError:
                form.add_error(
                    None,
                    "No se pudo registrar: la cédula o el nombre completo ya pertenecen a otro jugador.",
                )
            else:
                if limite_alcanzado:
                    form.add_error(
                        None,
                        f"Este equipo alcanzó el máximo de {limite_jugadores} jugadores.",
                    )
                else:
                    messages.success(
                        request,
                        f"El jugador «{jugador.nombre_completo}» fue registrado.",
                    )
                    return redirect(
                        "torneos:equipos:jugadores",
                        torneo_id=torneo_id,
                        equipo_id=equipo.pk,
                    )

    jugadores = equipo.jugadores.all()
    jugadores_registrados = jugadores.count()
    limite_jugadores = equipo.torneo.jugadores_maximos_por_equipo
    limite_alcanzado = (
        limite_jugadores is not None
        and jugadores_registrados >= limite_jugadores
    )

    return render(
        request,
        "equipos/jugadores.html",
        {
            "equipo": equipo,
            "torneo": equipo.torneo,
            "jugadores": jugadores,
            "jugadores_registrados": jugadores_registrados,
            "limite_jugadores": limite_jugadores,
            "limite_alcanzado": limite_alcanzado,
            "form": form,
        },
    )


@login_required
def editar_jugador(request, torneo_id, equipo_id, jugador_id):
    _require_administrator(request.user)
    jugador = get_object_or_404(
        Jugador.objects.select_related("equipo", "equipo__torneo"),
        pk=jugador_id,
        equipo_id=equipo_id,
        equipo__torneo_id=torneo_id,
    )
    equipo = jugador.equipo
    form = JugadorForm(
        request.POST if request.method == "POST" else None,
        instance=jugador,
    )

    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                jugador = form.save()
        except IntegrityError:
            form.add_error(
                None,
                "No se pudo guardar: la cédula o el nombre completo ya pertenecen a otro jugador.",
            )
        else:
            messages.success(
                request,
                f"Se actualizaron los datos de «{jugador.nombre_completo}».",
            )
            return redirect(
                "torneos:equipos:jugadores",
                torneo_id=torneo_id,
                equipo_id=equipo_id,
            )

    return render(
        request,
        "equipos/editar_jugador.html",
        {
            "equipo": equipo,
            "torneo": equipo.torneo,
            "jugador": jugador,
            "form": form,
        },
    )


@login_required
def eliminar_jugador(request, torneo_id, equipo_id, jugador_id):
    _require_administrator(request.user)
    jugador = get_object_or_404(
        Jugador.objects.select_related("equipo", "equipo__torneo"),
        pk=jugador_id,
        equipo_id=equipo_id,
        equipo__torneo_id=torneo_id,
    )

    if request.method == "POST":
        nombre = jugador.nombre_completo
        jugador.delete()
        messages.success(request, f"Se eliminó al jugador «{nombre}».")
        return redirect(
            "torneos:equipos:jugadores",
            torneo_id=torneo_id,
            equipo_id=equipo_id,
        )

    return render(
        request,
        "confirmar_eliminacion.html",
        {
            "titulo": "Eliminar jugador",
            "elemento": jugador.nombre_completo,
            "aviso": "Esta acción eliminará el registro del jugador y no se puede deshacer.",
            "url_cancelar": reverse(
                "torneos:equipos:jugadores",
                args=[torneo_id, equipo_id],
            ),
            "texto_confirmar": "Eliminar jugador",
        },
    )
