from functools import lru_cache
from itertools import combinations

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Encuentro, Jornada, Torneo


def crear_calendario_todos_contra_todos(torneo: Torneo) -> int:
    equipos = list(torneo.equipos.order_by("pk"))
    if len(equipos) < 2:
        raise ValueError("Se necesitan al menos dos equipos para crear el calendario.")
    if len(equipos) % 2:
        raise ValueError(
            "El torneo necesita una cantidad par de equipos. Agrega un equipo "
            "ficticio desde la gestión de equipos para completar el calendario."
        )

    if torneo.equipos_participantes and len(equipos) > torneo.equipos_participantes:
        raise ValueError(
            "Hay más equipos registrados que el máximo de participantes configurado."
        )

    with transaction.atomic():
        jornadas_existentes = list(torneo.jornadas.order_by("numero"))
        partidos_existentes = list(
            Encuentro.objects.filter(jornada__torneo=torneo)
            .select_related("jornada")
            .order_by("jornada__numero", "pk")
        )
        if jornadas_existentes or partidos_existentes:
            if not partidos_existentes:
                raise ValueError(
                    "Las jornadas existentes no contienen partidos que permitan "
                    "completar el calendario."
                )
            return _generar_despues_de_jornadas_anteriores(
                torneo,
                equipos,
                jornadas_existentes,
                partidos_existentes,
            )

        rotacion = equipos.copy()
        localias = _crear_historial_localias(equipos)
        historial_posiciones = _crear_historial_posiciones(equipos)
        equipos_por_id = {equipo.pk: equipo for equipo in equipos}
        equipo_ficticio_id = next(
            (equipo.pk for equipo in equipos if equipo.es_ficticio),
            None,
        )

        total_jornadas = len(rotacion) - 1
        for numero_jornada in range(total_jornadas):
            cruces = []
            equipo_libre = None

            for indice in range(len(rotacion) // 2):
                primero = rotacion[indice]
                segundo = rotacion[-(indice + 1)]
                cruces.append((primero.pk, segundo.pk))

            jornada = Jornada.objects.create(
                torneo=torneo,
                numero=numero_jornada + 1,
                equipo_libre=equipo_libre,
            )
            cruces = _asignar_localias(cruces, localias, jornada.numero)
            cruces = _ordenar_cruces_por_posicion(
                cruces,
                historial_posiciones,
                jornada.numero,
                equipo_ficticio_id,
            )
            Encuentro.objects.bulk_create(
                [
                    Encuentro(
                        jornada=jornada,
                        equipo_local=equipos_por_id[equipo_local_id],
                        equipo_visitante=equipos_por_id[equipo_visitante_id],
                        orden=orden,
                    )
                    for orden, (equipo_local_id, equipo_visitante_id) in enumerate(cruces)
                ]
            )
            rotacion = [rotacion[0], rotacion[-1], *rotacion[1:-1]]

    return total_jornadas


def _crear_historial_localias(equipos):
    return {
        equipo.pk: {"local": 0, "visitante": 0, "ultima": None}
        for equipo in equipos
    }


def _actualizar_historial_localias(localias, equipo_local_id, equipo_visitante_id):
    localias[equipo_local_id]["local"] += 1
    localias[equipo_local_id]["ultima"] = "local"
    localias[equipo_visitante_id]["visitante"] += 1
    localias[equipo_visitante_id]["ultima"] = "visitante"


def _cargar_historial_localias(equipos, partidos):
    localias = _crear_historial_localias(equipos)
    for partido in partidos:
        _actualizar_historial_localias(
            localias,
            partido.equipo_local_id,
            partido.equipo_visitante_id,
        )
    return localias


def _crear_historial_posiciones(equipos):
    return {
        equipo.pk: {"conteos": {}, "ultima": None}
        for equipo in equipos
    }


def _actualizar_historial_posiciones(historial, orden, equipo_local_id, equipo_visitante_id):
    for equipo_id in (equipo_local_id, equipo_visitante_id):
        posicion = historial[equipo_id]
        posicion["conteos"][orden] = posicion["conteos"].get(orden, 0) + 1
        posicion["ultima"] = orden


def _cargar_historial_posiciones(equipos, partidos, equipo_ficticio_id=None):
    historial = _crear_historial_posiciones(equipos)
    partidos_por_jornada = {}
    for partido in partidos:
        partidos_por_jornada.setdefault(partido.jornada_id, []).append(partido)

    for partidos_jornada in partidos_por_jornada.values():
        if equipo_ficticio_id is not None:
            partidos_jornada.sort(
                key=lambda partido: (
                    equipo_ficticio_id
                    in (partido.equipo_local_id, partido.equipo_visitante_id),
                    partido.orden,
                    partido.pk,
                )
            )
        else:
            partidos_jornada.sort(key=lambda partido: (partido.orden, partido.pk))
        for orden, partido in enumerate(partidos_jornada):
            _actualizar_historial_posiciones(
                historial,
                orden,
                partido.equipo_local_id,
                partido.equipo_visitante_id,
            )
    return historial


def _ordenar_cruces_por_posicion(
    cruces,
    historial,
    numero_jornada,
    equipo_ficticio_id=None,
):
    if not cruces:
        return []

    partido_ficticio = None
    if equipo_ficticio_id is not None:
        partido_ficticio = next(
            (
                cruce
                for cruce in cruces
                if equipo_ficticio_id in cruce
            ),
            None,
        )
        if partido_ficticio is not None:
            cruces = [cruce for cruce in cruces if cruce != partido_ficticio]

    cantidad_posiciones = len(cruces)

    if not cantidad_posiciones:
        _actualizar_historial_posiciones(
            historial,
            0,
            *partido_ficticio,
        )
        return [partido_ficticio]

    def costo(cruce, posicion):
        repeticiones = 0
        uso_acumulado = 0
        for equipo_id in cruce:
            datos = historial[equipo_id]
            repeticiones += datos["ultima"] == posicion
            uso_acumulado += datos["conteos"].get(posicion, 0)
        desempate = sum(cruce) + numero_jornada + posicion
        return repeticiones * 100 + uso_acumulado * 10 + desempate % cantidad_posiciones

    total_posiciones = cantidad_posiciones + (partido_ficticio is not None)
    asignaciones = _asignar_posiciones_optimas(cruces, cantidad_posiciones, costo)
    ordenados = [None] * total_posiciones
    for indice_cruce, posicion in enumerate(asignaciones):
        cruce = cruces[indice_cruce]
        ordenados[posicion] = cruce
        _actualizar_historial_posiciones(historial, posicion, *cruce)
    if partido_ficticio is not None:
        ultima_posicion = total_posiciones - 1
        ordenados[ultima_posicion] = partido_ficticio
        _actualizar_historial_posiciones(
            historial,
            ultima_posicion,
            *partido_ficticio,
        )
    return ordenados


def _asignar_posiciones_optimas(cruces, cantidad_posiciones, costo):
    if cantidad_posiciones > 12:
        asignaciones = [None] * cantidad_posiciones
        indices_disponibles = set(range(cantidad_posiciones))
        posiciones_libres = set(range(cantidad_posiciones))
        while indices_disponibles:
            _, indice_cruce, posicion = min(
                (
                    costo(cruces[indice], candidato),
                    indice,
                    candidato,
                )
                for indice in indices_disponibles
                for candidato in posiciones_libres
            )
            asignaciones[indice_cruce] = posicion
            indices_disponibles.remove(indice_cruce)
            posiciones_libres.remove(posicion)
        return asignaciones

    @lru_cache(maxsize=None)
    def mejor_costo(indice_cruce, posiciones_ocupadas):
        if indice_cruce == cantidad_posiciones:
            return 0
        return min(
            costo(cruces[indice_cruce], posicion)
            + mejor_costo(indice_cruce + 1, posiciones_ocupadas | (1 << posicion))
            for posicion in range(cantidad_posiciones)
            if not posiciones_ocupadas & (1 << posicion)
        )

    asignaciones = []
    ocupadas = 0
    for indice_cruce in range(cantidad_posiciones):
        opciones = [
            posicion
            for posicion in range(cantidad_posiciones)
            if not ocupadas & (1 << posicion)
        ]
        posicion = min(
            opciones,
            key=lambda candidato: (
                costo(cruces[indice_cruce], candidato)
                + mejor_costo(
                    indice_cruce + 1,
                    ocupadas | (1 << candidato),
                ),
                candidato,
            ),
        )
        asignaciones.append(posicion)
        ocupadas |= 1 << posicion
    return asignaciones


def _asignar_localias(cruces, localias, numero_jornada):
    orientados = []
    for equipo_a_id, equipo_b_id in cruces:
        opciones = [
            (equipo_a_id, equipo_b_id),
            (equipo_b_id, equipo_a_id),
        ]

        def costo(opcion):
            local_id, visitante_id = opcion
            estados = (
                (local_id, "local"),
                (visitante_id, "visitante"),
            )
            cambios_consecutivos = sum(
                localias[equipo_id]["ultima"] == rol
                for equipo_id, rol in estados
            )
            desequilibrio = sum(
                abs(
                    localias[equipo_id]["local"]
                    + (rol == "local")
                    - localias[equipo_id]["visitante"]
                    - (rol == "visitante")
                )
                for equipo_id, rol in estados
            )
            desempate = (
                (numero_jornada + equipo_a_id + equipo_b_id) % 2
                != (local_id == equipo_a_id)
            )
            return cambios_consecutivos, desequilibrio, desempate

        equipo_local_id, equipo_visitante_id = min(opciones, key=costo)
        _actualizar_historial_localias(
            localias,
            equipo_local_id,
            equipo_visitante_id,
        )
        orientados.append((equipo_local_id, equipo_visitante_id))
    return orientados


def crear_equipo_ficticio(torneo: Torneo):
    from equipos.models import Equipo

    with transaction.atomic():
        equipos = list(torneo.equipos.order_by("pk"))
        if not equipos:
            raise ValidationError("Registra al menos un equipo real primero.")
        if len(equipos) % 2 == 0:
            raise ValidationError("El torneo ya tiene una cantidad par de equipos.")
        if any(equipo.es_ficticio for equipo in equipos):
            raise ValidationError("Este torneo ya tiene un equipo ficticio.")
        if (
            torneo.equipos_participantes is not None
            and len(equipos) >= torneo.equipos_participantes
        ):
            raise ValidationError(
                "No hay un cupo disponible. Revisa la cantidad de participantes "
                "configurada para el torneo."
            )

        base_nombre = "FICTICIO - Equipo pendiente"
        nombre = base_nombre
        sufijo = 2
        while Equipo.objects.filter(torneo=torneo, nombre=nombre).exists():
            nombre = f"{base_nombre} {sufijo}"
            sufijo += 1
        ficticio = Equipo.objects.create(
            torneo=torneo,
            nombre=nombre,
            es_ficticio=True,
        )

        for jornada in torneo.jornadas.filter(equipo_libre__isnull=False):
            equipo_libre_id = jornada.equipo_libre_id
            Encuentro.objects.get_or_create(
                jornada=jornada,
                equipo_local_id=equipo_libre_id,
                equipo_visitante=ficticio,
            )
            jornada.equipo_libre = None
            jornada.save(update_fields=["equipo_libre"])
        return ficticio


def registrar_jornada_historica(torneo: Torneo, fecha_programada, partidos):
    equipos = list(torneo.equipos.order_by("pk"))
    if len(equipos) < 2 or len(equipos) % 2:
        raise ValidationError(
            "Completa primero la cantidad par de equipos, usando un equipo ficticio "
            "si hace falta."
        )
    if len(partidos) != len(equipos) // 2:
        raise ValidationError(
            f"La jornada debe tener exactamente {len(equipos) // 2} partidos."
        )

    participantes = []
    pares = []
    for partido in partidos:
        local = partido["equipo_local"]
        visitante = partido["equipo_visitante"]
        participantes.extend((local.pk, visitante.pk))
        pares.append(frozenset((local.pk, visitante.pk)))

    ids_equipos = {equipo.pk for equipo in equipos}
    if set(participantes) != ids_equipos or len(participantes) != len(ids_equipos):
        raise ValidationError(
            "Cada equipo, incluido el ficticio, debe aparecer exactamente una vez "
            "en la jornada."
        )
    if len(pares) != len(set(pares)):
        raise ValidationError("La jornada contiene enfrentamientos repetidos.")

    with transaction.atomic():
        existentes = Encuentro.objects.filter(jornada__torneo=torneo)
        total_enfrentamientos = len(equipos) * (len(equipos) - 1) // 2
        parejas_existentes = {
            frozenset((local_id, visitante_id))
            for local_id, visitante_id in existentes.values_list(
                "equipo_local_id",
                "equipo_visitante_id",
            )
        }
        if len(parejas_existentes) >= total_enfrentamientos:
            raise ValidationError(
                "El calendario ya contiene todos los enfrentamientos; registra "
                "solo resultados pendientes."
            )

        equipos_esperados = ids_equipos
        for jornada_existente in torneo.jornadas.all():
            participantes_existentes = [
                equipo_id
                for partido in jornada_existente.encuentros.all()
                for equipo_id in (
                    partido.equipo_local_id,
                    partido.equipo_visitante_id,
                )
            ]
            if (
                set(participantes_existentes) != equipos_esperados
                or len(participantes_existentes) != len(equipos_esperados)
            ):
                raise ValidationError(
                    f"La jornada {jornada_existente.numero} debe estar completa "
                    "antes de registrar la siguiente."
                )

        for par in pares:
            if par in parejas_existentes:
                raise ValidationError(
                    "Esta jornada contiene un enfrentamiento que ya se jugó en otra fecha."
                )

        numero = (torneo.jornadas.order_by("-numero").values_list("numero", flat=True).first() or 0) + 1
        jornada = Jornada.objects.create(
            torneo=torneo,
            numero=numero,
            fecha_programada=fecha_programada,
        )
        partidos_ordenados = sorted(
            partidos,
            key=lambda partido: any(
                equipo.es_ficticio
                for equipo in (partido["equipo_local"], partido["equipo_visitante"])
            ),
        )
        Encuentro.objects.bulk_create(
            [
                Encuentro(
                    jornada=jornada,
                    equipo_local=partido["equipo_local"],
                    equipo_visitante=partido["equipo_visitante"],
                    goles_local=partido.get("goles_local"),
                    goles_visitante=partido.get("goles_visitante"),
                    orden=orden,
                )
                for orden, partido in enumerate(partidos_ordenados)
            ]
        )
        return jornada


def _generar_despues_de_jornadas_anteriores(
    torneo,
    equipos,
    jornadas_existentes,
    partidos_existentes,
):
    pares_jugados = [
        frozenset((partido.equipo_local_id, partido.equipo_visitante_id))
        for partido in partidos_existentes
    ]
    if len(pares_jugados) != len(set(pares_jugados)):
        raise ValueError("Hay enfrentamientos repetidos en las jornadas anteriores.")

    for jornada in jornadas_existentes:
        participantes = []
        for partido in partidos_existentes:
            if partido.jornada_id == jornada.pk:
                participantes.extend((partido.equipo_local_id, partido.equipo_visitante_id))
        if len(participantes) != len(set(participantes)):
            raise ValueError(
                f"Un equipo aparece en más de un partido de la jornada {jornada.numero}."
            )

    equipos_por_id = {equipo.pk: equipo for equipo in equipos}
    if any(not pareja.issubset(equipos_por_id) for pareja in pares_jugados):
        raise ValueError("Todas las jornadas anteriores deben pertenecer a equipos registrados.")

    equipos_esperados = set(equipos_por_id)
    for jornada in jornadas_existentes:
        participantes = {
            equipo_id
            for partido in partidos_existentes
            if partido.jornada_id == jornada.pk
            for equipo_id in (
                partido.equipo_local_id,
                partido.equipo_visitante_id,
            )
        }
        if participantes != equipos_esperados:
            raise ValueError(
                f"La jornada {jornada.numero} no incluye exactamente a todos los equipos."
            )

    if len(equipos) % 2:
        for jornada in jornadas_existentes:
            participantes = {
                equipo_id
                for partido in partidos_existentes
                if partido.jornada_id == jornada.pk
                for equipo_id in (
                    partido.equipo_local_id,
                    partido.equipo_visitante_id,
                )
            }
            libres = set(equipos_por_id) - participantes
            if len(libres) == 1:
                jornada.equipo_libre_id = next(iter(libres))
                jornada.save(update_fields=["equipo_libre"])

    pares_jugados_set = set(pares_jugados)
    parejas_pendientes = [
        (pareja[0].pk, pareja[1].pk)
        for pareja in combinations(equipos, 2)
        if frozenset((pareja[0].pk, pareja[1].pk)) not in pares_jugados_set
    ]
    jornadas_pendientes = _descomponer_en_jornadas(equipos, parejas_pendientes)
    if jornadas_pendientes is None:
        raise ValueError(
            "No es posible completar el calendario con esas jornadas históricas "
            "sin dejar equipos libres. Revisa los cruces registrados."
        )

    ultima_jornada = max(jornada.numero for jornada in jornadas_existentes)
    localias = _cargar_historial_localias(
        equipos,
        sorted(
            partidos_existentes,
            key=lambda partido: (
                partido.jornada.numero,
                partido.orden,
                partido.pk,
            ),
        ),
    )
    equipo_ficticio_id = next(
        (equipo.pk for equipo in equipos if equipo.es_ficticio),
        None,
    )
    historial_posiciones = _cargar_historial_posiciones(
        equipos,
        sorted(
            partidos_existentes,
            key=lambda partido: (
                partido.jornada.numero,
                partido.orden,
                partido.pk,
            ),
        ),
        equipo_ficticio_id,
    )
    for indice, cruces in enumerate(jornadas_pendientes, start=1):
        jornada = Jornada.objects.create(
            torneo=torneo,
            numero=ultima_jornada + indice,
        )
        cruces = _asignar_localias(cruces, localias, jornada.numero)
        cruces = _ordenar_cruces_por_posicion(
            cruces,
            historial_posiciones,
            jornada.numero,
            equipo_ficticio_id,
        )
        Encuentro.objects.bulk_create(
            [
                Encuentro(
                    jornada=jornada,
                    equipo_local=equipos_por_id[equipo_local_id],
                    equipo_visitante=equipos_por_id[equipo_visitante_id],
                    orden=orden,
                )
                for orden, (equipo_local_id, equipo_visitante_id) in enumerate(cruces)
            ]
        )

    return torneo.jornadas.count()


def _descomponer_en_jornadas(equipos, parejas):
    pares_iniciales = frozenset(tuple(sorted(par)) for par in parejas)

    @lru_cache(maxsize=None)
    def resolver(pares_restantes):
        if not pares_restantes:
            return ()

        vecinos = {equipo.pk: set() for equipo in equipos}
        for local_id, visitante_id in pares_restantes:
            vecinos[local_id].add(visitante_id)
            vecinos[visitante_id].add(local_id)
        if any(len(opciones) != len(next(iter(vecinos.values()))) for opciones in vecinos.values()):
            return None

        def generar_emparejamientos(sin_asignar, seleccionados):
            if not sin_asignar:
                yield tuple(seleccionados)
                return

            equipo_id = min(
                sin_asignar,
                key=lambda candidato: (
                    len(vecinos[candidato] & sin_asignar),
                    candidato,
                ),
            )
            for rival_id in sorted(vecinos[equipo_id] & sin_asignar):
                yield from generar_emparejamientos(
                    sin_asignar - {equipo_id, rival_id},
                    [*seleccionados, (min(equipo_id, rival_id), max(equipo_id, rival_id))],
                )

        for emparejamiento in generar_emparejamientos(
            set(vecinos),
            [],
        ):
            pares_siguiente = pares_restantes - frozenset(emparejamiento)
            resto = resolver(pares_siguiente)
            if resto is not None:
                return (emparejamiento, *resto)
        return None

    return resolver(pares_iniciales)


def adaptar_calendario_al_ingresar_equipo(torneo: Torneo) -> int:
    equipos = list(torneo.equipos.order_by("pk"))
    jornadas = list(torneo.jornadas.order_by("numero"))

    if not jornadas:
        return 0

    with transaction.atomic():
        encuentros_existentes = list(
            Encuentro.objects.filter(jornada__torneo=torneo)
            .select_related("jornada")
            .order_by("jornada__numero", "orden", "pk")
        )
        parejas_existentes = {
            frozenset((partido.equipo_local_id, partido.equipo_visitante_id))
            for partido in encuentros_existentes
        }
        parejas_pendientes = [
            pareja
            for pareja in combinations(equipos, 2)
            if frozenset((pareja[0].pk, pareja[1].pk)) not in parejas_existentes
        ]
        jornadas_y_equipos_ocupados = [
            (
                jornada,
                {
                    equipo_id
                    for partido in encuentros_existentes
                    if partido.jornada_id == jornada.pk
                    for equipo_id in (
                        partido.equipo_local_id,
                        partido.equipo_visitante_id,
                    )
                },
            )
            for jornada in jornadas
        ]
        siguiente_numero = max(jornada.numero for jornada in jornadas) + 1
        cruces_nuevos_por_jornada = {}

        for equipo_a, equipo_b in parejas_pendientes:
            for jornada, ocupados in jornadas_y_equipos_ocupados:
                if equipo_a.pk not in ocupados and equipo_b.pk not in ocupados:
                    break
            else:
                jornada = Jornada.objects.create(
                    torneo=torneo,
                    numero=siguiente_numero,
                )
                siguiente_numero += 1
                ocupados = set()
                jornadas_y_equipos_ocupados.append((jornada, ocupados))

            cruces_nuevos_por_jornada.setdefault(jornada.pk, (jornada, []))[1].append(
                (equipo_a.pk, equipo_b.pk)
            )
            ocupados.update((equipo_a.pk, equipo_b.pk))

        localias = _crear_historial_localias(equipos)
        equipo_ficticio_id = next(
            (equipo.pk for equipo in equipos if equipo.es_ficticio),
            None,
        )
        historial_posiciones = _crear_historial_posiciones(equipos)
        partidos_por_jornada = {}
        for partido in encuentros_existentes:
            partidos_por_jornada.setdefault(partido.jornada_id, []).append(partido)

        partidos_nuevos = []
        partidos_reordenados = []
        equipos_por_id = {equipo.pk: equipo for equipo in equipos}
        for jornada, ocupados in sorted(
            jornadas_y_equipos_ocupados,
            key=lambda item: item[0].numero,
        ):
            partidos_jornada = partidos_por_jornada.get(jornada.pk, [])
            for partido in partidos_jornada:
                _actualizar_historial_localias(
                    localias,
                    partido.equipo_local_id,
                    partido.equipo_visitante_id,
                )
            cruces_nuevos = cruces_nuevos_por_jornada.get(jornada.pk, (None, []))[1]
            if not cruces_nuevos:
                if equipo_ficticio_id is not None:
                    partidos_ficticios = [
                        partido
                        for partido in partidos_jornada
                        if equipo_ficticio_id
                        in (partido.equipo_local_id, partido.equipo_visitante_id)
                    ]
                    if partidos_ficticios:
                        partidos_otros = [
                            partido
                            for partido in partidos_jornada
                            if partido not in partidos_ficticios
                        ]
                        for orden, partido in enumerate(
                            [*partidos_otros, *partidos_ficticios]
                        ):
                            partido.orden = orden
                            partidos_reordenados.append(partido)
                for partido in partidos_jornada:
                    _actualizar_historial_posiciones(
                        historial_posiciones,
                        partido.orden,
                        partido.equipo_local_id,
                        partido.equipo_visitante_id,
                    )
                continue
            cruces_orientados = _asignar_localias(
                cruces_nuevos,
                localias,
                jornada.numero,
            )
            cruces_existentes = [
                (partido.equipo_local_id, partido.equipo_visitante_id)
                for partido in partidos_jornada
            ]
            cruces_ordenados = _ordenar_cruces_por_posicion(
                [*cruces_existentes, *cruces_orientados],
                historial_posiciones,
                jornada.numero,
                equipo_ficticio_id,
            )
            partidos_por_cruce = {
                frozenset((partido.equipo_local_id, partido.equipo_visitante_id)): partido
                for partido in partidos_jornada
            }
            for orden, (local_id, visitante_id) in enumerate(cruces_ordenados):
                partido_existente = partidos_por_cruce.get(
                    frozenset((local_id, visitante_id))
                )
                if partido_existente:
                    partido_existente.orden = orden
                    partidos_reordenados.append(partido_existente)
                else:
                    partidos_nuevos.append(
                        Encuentro(
                            jornada=jornada,
                            equipo_local=equipos_por_id[local_id],
                            equipo_visitante=equipos_por_id[visitante_id],
                            orden=orden,
                        )
                    )

        Encuentro.objects.bulk_create(partidos_nuevos)
        if partidos_reordenados:
            Encuentro.objects.bulk_update(partidos_reordenados, ["orden"])

    return torneo.jornadas.count()


def _agendar_enfrentamientos(
    torneo,
    equipos,
    jornadas_existentes,
    partidos_fijos,
    parejas_pendientes=None,
):
    cantidad_jornadas_minima = max(len(equipos) - 1, len(jornadas_existentes))
    jornadas = list(jornadas_existentes)

    while len(jornadas) < cantidad_jornadas_minima:
        jornadas.append(
            Jornada.objects.create(
                torneo=torneo,
                numero=len(jornadas) + 1,
            )
        )

    ocupados_por_jornada = [set() for _ in jornadas]
    jornadas_anteriores_fijadas = set()
    for partido in partidos_fijos:
        indice = jornadas.index(partido.jornada)
        jornadas_anteriores_fijadas.add(indice)
        ocupados_por_jornada[indice].update(
            (partido.equipo_local_id, partido.equipo_visitante_id)
        )

    if parejas_pendientes is None:
        parejas_pendientes = list(combinations(equipos, 2))

    orden_calendario = _ordenar_parejas_por_jornada(equipos)
    parejas_pendientes.sort(
        key=lambda pareja: (
            orden_calendario[
                frozenset((pareja[0].pk, pareja[1].pk))
            ],
            pareja[0].pk,
            pareja[1].pk,
        )
    )

    partidos_nuevos = []
    for equipo_a, equipo_b in parejas_pendientes:
        preferida = orden_calendario[
            frozenset((equipo_a.pk, equipo_b.pk))
        ]
        indices = sorted(
            (
                indice
                for indice in range(len(ocupados_por_jornada))
                if indice not in jornadas_anteriores_fijadas
            ),
            key=lambda indice: (
                indice != preferida,
                len(ocupados_por_jornada[indice]),
                indice,
            ),
        )
        for indice in indices:
            ocupados = ocupados_por_jornada[indice]
            if equipo_a.pk not in ocupados and equipo_b.pk not in ocupados:
                jornada = jornadas[indice]
                local, visitante = (
                    (equipo_a, equipo_b)
                    if (jornada.numero + equipo_a.pk + equipo_b.pk) % 2 == 0
                    else (equipo_b, equipo_a)
                )
                partidos_nuevos.append(
                    Encuentro(
                        jornada=jornada,
                        equipo_local=local,
                        equipo_visitante=visitante,
                    )
                )
                ocupados.update((equipo_a.pk, equipo_b.pk))
                break
        else:
            jornada = Jornada.objects.create(
                torneo=torneo,
                numero=len(jornadas) + 1,
            )
            jornadas.append(jornada)
            ocupados_por_jornada.append({equipo_a.pk, equipo_b.pk})
            local, visitante = (
                (equipo_a, equipo_b)
                if (jornada.numero + equipo_a.pk + equipo_b.pk) % 2 == 0
                else (equipo_b, equipo_a)
            )
            partidos_nuevos.append(
                Encuentro(
                    jornada=jornada,
                    equipo_local=local,
                    equipo_visitante=visitante,
                )
            )

    Encuentro.objects.bulk_create(partidos_nuevos)

    for indice, jornada in enumerate(jornadas):
        if indice in jornadas_anteriores_fijadas:
            continue
        equipos_activos = {equipo.pk for equipo in equipos}
        libres = equipos_activos - ocupados_por_jornada[indice]
        jornada.equipo_libre_id = (
            next(iter(libres))
            if len(equipos) % 2 == 1 and len(libres) == 1
            else None
        )
        jornada.save(update_fields=["equipo_libre"])


def _ordenar_parejas_por_jornada(equipos):
    rotacion = equipos.copy()
    if len(rotacion) % 2:
        rotacion.append(None)

    orden = {}
    for numero_jornada in range(len(rotacion) - 1):
        for indice in range(len(rotacion) // 2):
            primero = rotacion[indice]
            segundo = rotacion[-(indice + 1)]
            if primero is not None and segundo is not None:
                orden[frozenset((primero.pk, segundo.pk))] = numero_jornada
        rotacion = [rotacion[0], rotacion[-1], *rotacion[1:-1]]
    return orden
