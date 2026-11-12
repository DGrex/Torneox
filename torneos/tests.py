from datetime import date

from django.test import TestCase

from django.urls import reverse

from equipos.models import Equipo
from usuarios.models import Usuario

from .models import Encuentro, Jornada, Torneo
from .services import (
    adaptar_calendario_al_ingresar_equipo,
    crear_equipo_ficticio,
)


class ConfiguracionTorneoTests(TestCase):
    def setUp(self):
        self.administrador = Usuario.objects.create_user(
            username="admin-torneo",
            password="ClaveSegura123!",
            rol=Usuario.Rol.ADMINISTRADOR,
        )
        self.dirigente = Usuario.objects.create_user(
            username="dirigente",
            password="ClaveSegura123!",
            rol=Usuario.Rol.DIRIGENTE,
        )

    def test_solo_administradores_pueden_ver_la_configuracion(self):
        url = reverse("torneos:lista")

        respuesta_anonima = self.client.get(url)
        self.assertRedirects(
            respuesta_anonima,
            f"{reverse('usuarios:login')}?next={url}",
        )

        self.client.force_login(self.dirigente)
        respuesta_dirigente = self.client.get(url)
        self.assertEqual(respuesta_dirigente.status_code, 403)

    def test_administrador_crea_torneo_con_reglas_configurables(self):
        self.client.force_login(self.administrador)

        respuesta = self.client.post(
            reverse("torneos:lista"),
            {
                "nombre": "Copa de Prueba",
                "equipos_participantes": 12,
                "equipos_clasificados": 8,
                "jugadores_maximos_por_equipo": 25,
                "bonificacion_habilitada": "on",
            },
        )

        self.assertRedirects(respuesta, reverse("torneos:lista"))
        torneo = Torneo.objects.get(nombre="Copa de Prueba")
        self.assertEqual(torneo.equipos_participantes, 12)
        self.assertEqual(torneo.equipos_clasificados, 8)
        self.assertEqual(torneo.jugadores_maximos_por_equipo, 25)
        self.assertTrue(torneo.bonificacion_habilitada)

    def test_administrador_puede_editar_las_reglas(self):
        torneo = Torneo.objects.create(
            nombre="Torneo inicial",
            equipos_participantes=10,
            equipos_clasificados=4,
            jugadores_maximos_por_equipo=20,
        )
        self.client.force_login(self.administrador)

        respuesta = self.client.post(
            reverse("torneos:editar", args=[torneo.pk]),
            {
                "nombre": "Torneo actualizado",
                "equipos_participantes": 14,
                "equipos_clasificados": 6,
                "jugadores_maximos_por_equipo": 22,
                "bonificacion_habilitada": "on",
            },
        )

        self.assertRedirects(respuesta, reverse("torneos:lista"))
        torneo.refresh_from_db()
        self.assertEqual(torneo.nombre, "Torneo actualizado")
        self.assertEqual(torneo.equipos_participantes, 14)
        self.assertEqual(torneo.equipos_clasificados, 6)
        self.assertEqual(torneo.jugadores_maximos_por_equipo, 22)
        self.assertTrue(torneo.bonificacion_habilitada)

    def test_administrador_puede_eliminar_torneo_y_datos_relacionados(self):
        torneo = Torneo.objects.create(nombre="Torneo para eliminar")
        equipo_a = Equipo.objects.create(torneo=torneo, nombre="Equipo A")
        equipo_b = Equipo.objects.create(torneo=torneo, nombre="Equipo B")
        jornada = Jornada.objects.create(torneo=torneo, numero=1)
        Encuentro.objects.create(
            jornada=jornada,
            equipo_local=equipo_a,
            equipo_visitante=equipo_b,
            goles_local=1,
            goles_visitante=0,
        )
        url = reverse("torneos:eliminar", args=[torneo.pk])
        self.client.force_login(self.administrador)

        confirmacion = self.client.get(url)
        self.assertEqual(confirmacion.status_code, 200)
        self.assertTrue(Torneo.objects.filter(pk=torneo.pk).exists())
        self.assertContains(confirmacion, "jugadores")

        respuesta = self.client.post(url)

        self.assertRedirects(respuesta, reverse("torneos:lista"))
        self.assertFalse(Torneo.objects.filter(pk=torneo.pk).exists())
        self.assertFalse(Equipo.objects.filter(torneo=torneo).exists())
        self.assertFalse(Jornada.objects.filter(torneo=torneo).exists())
        self.assertFalse(Encuentro.objects.filter(jornada__torneo=torneo).exists())

    def test_interfaz_muestra_regla_de_todos_contra_todos_y_bonificaciones(self):
        self.client.force_login(self.administrador)

        respuesta = self.client.get(reverse("torneos:lista"))

        self.assertContains(respuesta, "todos los equipos inscritos")
        self.assertContains(respuesta, "+2 puntos")
        self.assertContains(respuesta, "+1 punto")

    def test_no_permite_cero_equipos_clasificados(self):
        self.client.force_login(self.administrador)

        respuesta = self.client.post(
            reverse("torneos:lista"),
            {"nombre": "Torneo inválido", "equipos_clasificados": 0},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Torneo.objects.filter(nombre="Torneo inválido").exists())

    def test_campos_de_participantes_y_clasificados_son_opcionales_y_se_recuerdan(self):
        self.client.force_login(self.administrador)

        respuesta = self.client.post(
            reverse("torneos:lista"),
            {"nombre": "Torneo por definir"},
        )

        self.assertRedirects(respuesta, reverse("torneos:lista"))
        torneo = Torneo.objects.get(nombre="Torneo por definir")
        self.assertIsNone(torneo.equipos_participantes)
        self.assertIsNone(torneo.equipos_clasificados)

        respuesta = self.client.get(reverse("torneos:lista"))
        self.assertContains(respuesta, "Pendiente: definir cuántos equipos participarán")
        self.assertContains(respuesta, "Pendiente: definir cuántos equipos clasificarán")
        self.assertContains(respuesta, "Pendiente: definir el máximo de jugadores por equipo")

    def test_no_permite_cero_jugadores_maximos_por_equipo(self):
        self.client.force_login(self.administrador)

        respuesta = self.client.post(
            reverse("torneos:lista"),
            {
                "nombre": "Torneo inválido",
                "jugadores_maximos_por_equipo": 0,
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Torneo.objects.filter(nombre="Torneo inválido").exists())


class CalendarioTorneoTests(TestCase):
    def setUp(self):
        self.administrador = Usuario.objects.create_user(
            username="admin-calendario",
            password="ClaveSegura123!",
            rol=Usuario.Rol.ADMINISTRADOR,
        )
        self.dirigente = Usuario.objects.create_user(
            username="dirigente-calendario",
            password="ClaveSegura123!",
            rol=Usuario.Rol.DIRIGENTE,
        )
        self.torneo = Torneo.objects.create(
            nombre="Copa Calendario",
            equipos_participantes=12,
        )
        self.url = reverse("torneos:gestionar", args=[self.torneo.pk])
        self.generar_url = reverse("torneos:generar_calendario", args=[self.torneo.pk])

    def crear_equipos(self, cantidad):
        return [
            Equipo.objects.create(torneo=self.torneo, nombre=f"Equipo {numero:02d}")
            for numero in range(1, cantidad + 1)
        ]

    def test_once_equipos_generan_calendario_completo_con_ficticio(self):
        equipos = self.crear_equipos(11)
        ficticio = crear_equipo_ficticio(self.torneo)
        self.client.force_login(self.administrador)

        respuesta = self.client.post(self.generar_url)

        self.assertRedirects(respuesta, self.url)
        jornadas = list(Jornada.objects.filter(torneo=self.torneo).order_by("numero"))
        encuentros = list(
            Encuentro.objects.filter(jornada__torneo=self.torneo).select_related(
                "jornada",
                "equipo_local",
                "equipo_visitante",
            )
        )
        self.assertEqual(len(jornadas), 11)
        self.assertEqual(len(encuentros), 66)
        self.assertTrue(all(jornada.equipo_libre_id is None for jornada in jornadas))
        self.assertTrue(all(jornada.encuentros.count() == 6 for jornada in jornadas))

        pares = {
            frozenset((encuentro.equipo_local_id, encuentro.equipo_visitante_id))
            for encuentro in encuentros
        }
        self.assertEqual(len(pares), 66)
        self.assertTrue(ficticio.es_ficticio)
        for jornada in jornadas:
            ultimo_partido = jornada.encuentros.order_by("orden").last()
            self.assertIn(
                ficticio.pk,
                (ultimo_partido.equipo_local_id, ultimo_partido.equipo_visitante_id),
            )

    def test_doce_equipos_generan_jornadas_sin_equipos_libres(self):
        self.crear_equipos(12)
        self.client.force_login(self.administrador)

        self.client.post(self.generar_url)

        jornadas = list(Jornada.objects.filter(torneo=self.torneo))
        self.assertEqual(len(jornadas), 11)
        self.assertTrue(all(jornada.equipo_libre_id is None for jornada in jornadas))
        self.assertEqual(Encuentro.objects.filter(jornada__torneo=self.torneo).count(), 66)
        self.assertTrue(all(jornada.encuentros.count() == 6 for jornada in jornadas))

    def test_partidos_generados_usan_posiciones_distintas_por_equipo(self):
        equipos = self.crear_equipos(6)
        self.client.force_login(self.administrador)

        self.client.post(self.generar_url)

        posiciones_por_equipo = {equipo.pk: [] for equipo in equipos}
        for jornada in Jornada.objects.filter(torneo=self.torneo).order_by("numero"):
            for orden, partido in enumerate(jornada.encuentros.all()):
                posiciones_por_equipo[partido.equipo_local_id].append(orden)
                posiciones_por_equipo[partido.equipo_visitante_id].append(orden)

        self.assertTrue(
            all(
                all(
                    posicion_anterior != posicion_actual
                    for posicion_anterior, posicion_actual in zip(posiciones, posiciones[1:])
                )
                for posiciones in posiciones_por_equipo.values()
            ),
            "Cada equipo debería cambiar de posición en cada jornada cuando sea posible.",
        )

    def test_calendario_solo_puede_generarse_una_vez(self):
        self.crear_equipos(4)
        self.client.force_login(self.administrador)
        self.client.post(self.generar_url)

        segunda_respuesta = self.client.post(self.generar_url)

        self.assertRedirects(segunda_respuesta, self.url)
        self.assertEqual(Jornada.objects.filter(torneo=self.torneo).count(), 3)
        self.assertEqual(Encuentro.objects.filter(jornada__torneo=self.torneo).count(), 6)

    def test_puede_reemplazar_calendario_pendiente_para_cargar_jornadas_historicas(self):
        equipos = self.crear_equipos(4)
        self.client.force_login(self.administrador)
        self.client.post(self.generar_url)
        reemplazar_url = reverse(
            "torneos:reemplazar_calendario_por_historicas",
            args=[self.torneo.pk],
        )

        confirmacion = self.client.get(reemplazar_url)
        respuesta = self.client.post(reemplazar_url)

        self.assertEqual(confirmacion.status_code, 200)
        self.assertRedirects(respuesta, self.url)
        self.assertEqual(self.torneo.equipos.count(), len(equipos))
        self.assertFalse(Jornada.objects.filter(torneo=self.torneo).exists())
        self.assertFalse(Encuentro.objects.filter(jornada__torneo=self.torneo).exists())

    def test_no_puede_reemplazar_calendario_con_resultados(self):
        equipos = self.crear_equipos(2)
        self.client.force_login(self.administrador)
        self.client.post(self.generar_url)
        partido = Encuentro.objects.get(jornada__torneo=self.torneo)
        partido.goles_local = 1
        partido.goles_visitante = 0
        partido.save(update_fields=["goles_local", "goles_visitante"])
        reemplazar_url = reverse(
            "torneos:reemplazar_calendario_por_historicas",
            args=[self.torneo.pk],
        )

        respuesta = self.client.post(reemplazar_url)

        self.assertRedirects(respuesta, self.url)
        self.assertTrue(Jornada.objects.filter(torneo=self.torneo).exists())
        self.assertTrue(Encuentro.objects.filter(pk=partido.pk).exists())

    def test_completa_enfrentamientos_pendientes_sin_duplicar_partidos_existentes(self):
        equipos = self.crear_equipos(4)
        jornada = Jornada.objects.create(torneo=self.torneo, numero=1)
        partidos_existentes = [
            Encuentro.objects.create(
                jornada=jornada,
                equipo_local=equipos[0],
                equipo_visitante=equipos[1],
            ),
            Encuentro.objects.create(
                jornada=jornada,
                equipo_local=equipos[2],
                equipo_visitante=equipos[3],
            ),
        ]
        self.client.force_login(self.administrador)

        respuesta = self.client.post(self.generar_url)

        self.assertRedirects(respuesta, self.url)
        self.assertTrue(
            all(Encuentro.objects.filter(pk=partido.pk).exists() for partido in partidos_existentes)
        )
        partidos = list(Encuentro.objects.filter(jornada__torneo=self.torneo))
        pares = {
            frozenset((partido.equipo_local_id, partido.equipo_visitante_id))
            for partido in partidos
        }
        self.assertEqual(len(partidos), 6)
        self.assertEqual(len(pares), 6)
        for jornada in Jornada.objects.filter(torneo=self.torneo):
            participantes = [
                equipo_id
                for partido in jornada.encuentros.all()
                for equipo_id in (partido.equipo_local_id, partido.equipo_visitante_id)
            ]
            self.assertEqual(len(participantes), len(set(participantes)))

    def test_calendario_requiere_dos_equipos(self):
        self.crear_equipos(1)
        self.client.force_login(self.administrador)

        respuesta = self.client.post(self.generar_url)

        self.assertRedirects(respuesta, self.url)
        self.assertFalse(Jornada.objects.filter(torneo=self.torneo).exists())

    def test_dirigente_no_administrador_no_puede_generar_calendario(self):
        self.crear_equipos(2)
        self.client.force_login(self.dirigente)

        respuesta = self.client.post(self.generar_url)

        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(Jornada.objects.filter(torneo=self.torneo).exists())

    def test_el_panel_muestra_jornadas_partidos_y_equipo_libre(self):
        self.crear_equipos(4)
        self.client.force_login(self.administrador)
        self.client.post(self.generar_url)

        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Calendario generado")
        self.assertContains(respuesta, "Jornada 1")
        self.assertContains(respuesta, "<details")
        self.assertContains(respuesta, "0/2 resultados")
        self.assertContains(respuesta, "Todos los equipos")

    def test_administrador_puede_programar_jornada_y_registrar_resultado(self):
        self.crear_equipos(2)
        self.client.force_login(self.administrador)
        self.client.post(self.generar_url)
        jornada = Jornada.objects.get(torneo=self.torneo)
        encuentro = jornada.encuentros.get()

        respuesta_fecha = self.client.post(
            reverse(
                "torneos:actualizar_fecha_jornada",
                args=[self.torneo.pk, jornada.pk],
            ),
            {"fecha_programada": "2026-11-20"},
        )
        respuesta_resultado = self.client.post(
            reverse(
                "torneos:actualizar_resultado",
                args=[self.torneo.pk, encuentro.pk],
            ),
            {"goles_local": 2, "goles_visitante": 1},
        )

        self.assertRedirects(respuesta_fecha, self.url)
        self.assertRedirects(respuesta_resultado, self.url)
        jornada.refresh_from_db()
        encuentro.refresh_from_db()
        self.assertEqual(jornada.fecha_programada, date(2026, 11, 20))
        self.assertEqual((encuentro.goles_local, encuentro.goles_visitante), (2, 1))
        self.assertTrue(encuentro.jugado)

    def test_no_permite_mover_el_partido_ficticio_del_final(self):
        self.crear_equipos(3)
        ficticio = crear_equipo_ficticio(self.torneo)
        self.client.force_login(self.administrador)
        self.client.post(self.generar_url)
        jornada = Jornada.objects.get(torneo=self.torneo, numero=1)
        partidos = list(jornada.encuentros.order_by("orden"))
        partido_ficticio = next(
            partido
            for partido in partidos
            if ficticio.pk in (partido.equipo_local_id, partido.equipo_visitante_id)
        )
        url = reverse(
            "torneos:reordenar_encuentros",
            args=[self.torneo.pk, jornada.pk],
        )

        respuesta = self.client.post(
            url,
            {
                "orden_ids": ",".join(
                    [str(partido_ficticio.pk)]
                    + [
                        str(partido.pk)
                        for partido in partidos
                        if partido.pk != partido_ficticio.pk
                    ]
                )
            },
            follow=True,
        )

        self.assertContains(respuesta, "debe permanecer al final")
        self.assertEqual(
            jornada.encuentros.order_by("orden").last().pk,
            partido_ficticio.pk,
        )

    def test_panel_resalta_partido_ficticio_y_no_ofrece_eliminar_partidos(self):
        self.crear_equipos(3)
        crear_equipo_ficticio(self.torneo)
        self.client.force_login(self.administrador)
        self.client.post(self.generar_url)

        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, "Partido con equipo ficticio")
        self.assertNotContains(respuesta, "Eliminar partido pendiente")

    def test_jornada_historica_guarda_partido_ficticio_al_final(self):
        equipos = self.crear_equipos(3)
        ficticio = crear_equipo_ficticio(self.torneo)
        self.client.force_login(self.administrador)

        respuesta = self.client.post(
            reverse("torneos:registrar_jornada_anterior", args=[self.torneo.pk]),
            {
                "fecha_programada": "2026-10-25",
                "form-TOTAL_FORMS": "2",
                "form-INITIAL_FORMS": "0",
                "form-MIN_NUM_FORMS": "2",
                "form-MAX_NUM_FORMS": "2",
                "form-0-equipo_local": ficticio.pk,
                "form-0-equipo_visitante": equipos[0].pk,
                "form-1-equipo_local": equipos[1].pk,
                "form-1-equipo_visitante": equipos[2].pk,
            },
        )

        self.assertRedirects(respuesta, self.url)
        jornada = Jornada.objects.get(torneo=self.torneo)
        ultimo_partido = jornada.encuentros.order_by("orden").last()
        self.assertIn(
            ficticio.pk,
            (ultimo_partido.equipo_local_id, ultimo_partido.equipo_visitante_id),
        )

    def test_registra_jornadas_anteriores_y_genera_solo_enfrentamientos_pendientes(self):
        equipos = self.crear_equipos(4)
        self.client.force_login(self.administrador)
        respuesta = self.client.post(
            reverse("torneos:registrar_jornada_anterior", args=[self.torneo.pk]),
            {
                "fecha_programada": "2026-10-25",
                "form-TOTAL_FORMS": "2",
                "form-INITIAL_FORMS": "0",
                "form-MIN_NUM_FORMS": "2",
                "form-MAX_NUM_FORMS": "2",
                "form-0-equipo_local": equipos[0].pk,
                "form-0-equipo_visitante": equipos[1].pk,
                "form-1-equipo_local": equipos[2].pk,
                "form-1-equipo_visitante": equipos[3].pk,
            },
        )
        self.assertRedirects(respuesta, self.url)

        panel = self.client.get(self.url)
        self.assertContains(panel, "Registrar una fecha ya jugada")
        self.assertContains(panel, "Generar jornadas restantes")

        jornada_anterior = Jornada.objects.get(torneo=self.torneo, numero=1)
        partidos_anteriores = list(jornada_anterior.encuentros.all())
        ids_anteriores = {partido.pk for partido in partidos_anteriores}
        self.assertEqual(jornada_anterior.fecha_programada, date(2026, 10, 25))
        self.assertEqual(len(partidos_anteriores), 2)

        respuesta_generacion = self.client.post(self.generar_url)

        self.assertRedirects(respuesta_generacion, self.url)
        jornada_anterior.refresh_from_db()
        partidos = list(
            Encuentro.objects.filter(jornada__torneo=self.torneo).select_related(
                "jornada"
            )
        )
        self.assertEqual(jornada_anterior.fecha_programada, date(2026, 10, 25))
        self.assertEqual(len(partidos), 6)
        self.assertEqual(sum(partido.jugado for partido in partidos), 0)
        self.assertEqual(
            len({
                frozenset((partido.equipo_local_id, partido.equipo_visitante_id))
                for partido in partidos
            }),
            6,
        )
        self.assertTrue(
            all(
                partido.jornada.numero > jornada_anterior.numero
                for partido in partidos
                if partido.pk not in ids_anteriores
            )
        )
        self.assertTrue(
            all(
                partido.jornada.numero == jornada_anterior.numero
                for partido in partidos
                if partido.pk in ids_anteriores
            )
        )

        partido_historico = partidos_anteriores[0]
        respuesta_resultado = self.client.post(
            reverse(
                "torneos:actualizar_resultado",
                args=[self.torneo.pk, partido_historico.pk],
            ),
            {"goles_local": 2, "goles_visitante": 1},
        )
        self.assertRedirects(respuesta_resultado, self.url)
        partido_historico.refresh_from_db()
        self.assertEqual(
            (partido_historico.goles_local, partido_historico.goles_visitante),
            (2, 1),
        )

    def test_registra_dos_jornadas_sin_resultados_y_genera_despues_de_ellas(self):
        equipos = self.crear_equipos(6)
        self.client.force_login(self.administrador)
        registro_url = reverse("torneos:registrar_jornada_anterior", args=[self.torneo.pk])
        cruces_por_jornada = [
            [(equipos[0], equipos[1]), (equipos[2], equipos[3]), (equipos[4], equipos[5])],
            [(equipos[0], equipos[2]), (equipos[1], equipos[4]), (equipos[3], equipos[5])],
        ]
        fechas = [date(2026, 10, 25), date(2026, 11, 1)]
        jornadas_guardadas = []

        for numero, (fecha, cruces) in enumerate(
            zip(fechas, cruces_por_jornada),
            start=1,
        ):
            datos = {
                "fecha_programada": fecha.isoformat(),
                "form-TOTAL_FORMS": "3",
                "form-INITIAL_FORMS": "0",
                "form-MIN_NUM_FORMS": "3",
                "form-MAX_NUM_FORMS": "3",
            }
            for indice, (local, visitante) in enumerate(cruces):
                datos[f"form-{indice}-equipo_local"] = local.pk
                datos[f"form-{indice}-equipo_visitante"] = visitante.pk

            respuesta = self.client.post(registro_url, datos)
            self.assertRedirects(respuesta, self.url)
            jornadas_guardadas.append(Jornada.objects.get(torneo=self.torneo, numero=numero))

        partidos_historicos = [
            partido
            for jornada in jornadas_guardadas
            for partido in jornada.encuentros.all()
        ]
        cruces_historicos = {
            frozenset((partido.equipo_local_id, partido.equipo_visitante_id))
            for partido in partidos_historicos
        }
        self.assertEqual(len(partidos_historicos), 6)
        self.assertTrue(all(not partido.jugado for partido in partidos_historicos))
        self.assertContains(self.client.get(self.url), "Guardar resultado")

        respuesta_generacion = self.client.post(self.generar_url)

        self.assertRedirects(respuesta_generacion, self.url)
        todos_los_partidos = list(Encuentro.objects.filter(jornada__torneo=self.torneo))
        cruces_totales = {
            frozenset((partido.equipo_local_id, partido.equipo_visitante_id))
            for partido in todos_los_partidos
        }
        self.assertEqual(len(todos_los_partidos), 15)
        self.assertEqual(len(cruces_totales), 15)
        self.assertTrue(cruces_historicos.issubset(cruces_totales))
        for jornada in jornadas_guardadas:
            jornada.refresh_from_db()
            self.assertEqual(jornada.fecha_programada, fechas[jornada.numero - 1])
            self.assertEqual(jornada.encuentros.count(), 3)
            self.assertTrue(
                all(
                    not partido.jugado
                    for partido in jornada.encuentros.all()
                )
            )
        self.assertTrue(
            all(
                partido.jornada.numero > 2
                for partido in todos_los_partidos
                if partido not in partidos_historicos
            )
        )
        for jornada in Jornada.objects.filter(torneo=self.torneo):
            participantes = [
                equipo_id
                for partido in jornada.encuentros.all()
                for equipo_id in (partido.equipo_local_id, partido.equipo_visitante_id)
            ]
            self.assertEqual(set(participantes), {equipo.pk for equipo in equipos})
            self.assertEqual(len(participantes), len(set(participantes)))

    def test_jornadas_generadas_alternan_localia_sin_cambiar_jornadas_historicas(self):
        equipos = self.crear_equipos(6)
        cruces_historicos = [
            [(equipos[0], equipos[1]), (equipos[2], equipos[3]), (equipos[4], equipos[5])],
            [(equipos[2], equipos[0]), (equipos[1], equipos[4]), (equipos[3], equipos[5])],
        ]
        self.client.force_login(self.administrador)
        registro_url = reverse("torneos:registrar_jornada_anterior", args=[self.torneo.pk])

        fechas_historicas = [date(2026, 10, 25), date(2026, 11, 1)]
        for numero, cruces in enumerate(cruces_historicos, start=1):
            datos = {
                "fecha_programada": fechas_historicas[numero - 1].isoformat(),
                "form-TOTAL_FORMS": "3",
                "form-INITIAL_FORMS": "0",
                "form-MIN_NUM_FORMS": "3",
                "form-MAX_NUM_FORMS": "3",
            }
            for indice, (local, visitante) in enumerate(cruces):
                datos[f"form-{indice}-equipo_local"] = local.pk
                datos[f"form-{indice}-equipo_visitante"] = visitante.pk
            respuesta = self.client.post(registro_url, datos)
            self.assertRedirects(respuesta, self.url)

        localias_historicas = {
            jornada.numero: {
                (partido.equipo_local_id, partido.equipo_visitante_id)
                for partido in jornada.encuentros.all()
            }
            for jornada in Jornada.objects.filter(torneo=self.torneo)
        }
        self.client.post(self.generar_url)

        localias_anteriores = {}
        for partido in Encuentro.objects.filter(
            jornada__torneo=self.torneo,
            jornada__numero__lte=2,
        ).select_related("jornada").order_by("jornada__numero", "pk"):
            self.assertIn(
                (partido.equipo_local_id, partido.equipo_visitante_id),
                localias_historicas[partido.jornada.numero],
            )
            localias_anteriores[partido.equipo_local_id] = "local"
            localias_anteriores[partido.equipo_visitante_id] = "visitante"

        for jornada in Jornada.objects.filter(
            torneo=self.torneo,
            numero__gt=2,
        ).order_by("numero"):
            for partido in jornada.encuentros.all():
                local_anterior = localias_anteriores.get(partido.equipo_local_id)
                visitante_anterior = localias_anteriores.get(partido.equipo_visitante_id)
                repeticiones_actuales = (
                    local_anterior == "local"
                ) + (
                    visitante_anterior == "visitante"
                )
                repeticiones_invertidas = (
                    local_anterior == "visitante"
                ) + (
                    visitante_anterior == "local"
                )
                self.assertLessEqual(
                    repeticiones_actuales,
                    repeticiones_invertidas,
                    "La localía debe minimizar repeticiones consecutivas cuando sea posible.",
                )
                localias_anteriores[partido.equipo_local_id] = "local"
                localias_anteriores[partido.equipo_visitante_id] = "visitante"

    def test_puede_guardar_orden_de_partidos_sin_alterar_cruces(self):
        self.crear_equipos(4)
        self.client.force_login(self.administrador)
        self.client.post(self.generar_url)
        jornada = Jornada.objects.get(torneo=self.torneo, numero=1)
        partidos = list(jornada.encuentros.all())
        cruces_originales = {
            partido.pk: (partido.equipo_local_id, partido.equipo_visitante_id)
            for partido in partidos
        }
        orden_url = reverse(
            "torneos:reordenar_encuentros",
            args=[self.torneo.pk, jornada.pk],
        )

        respuesta = self.client.post(
            orden_url,
            {"orden_ids": ",".join(str(partido.pk) for partido in reversed(partidos))},
        )

        self.assertRedirects(respuesta, self.url)
        partidos_ordenados = list(jornada.encuentros.all())
        self.assertEqual(
            [partido.pk for partido in partidos_ordenados],
            [partido.pk for partido in reversed(partidos)],
        )
        self.assertEqual(
            {
                partido.pk: (partido.equipo_local_id, partido.equipo_visitante_id)
                for partido in partidos_ordenados
            },
            cruces_originales,
        )

    def test_rechaza_orden_de_partidos_incompleto_o_con_duplicados(self):
        self.crear_equipos(4)
        self.client.force_login(self.administrador)
        self.client.post(self.generar_url)
        jornada = Jornada.objects.get(torneo=self.torneo, numero=1)
        partidos = list(jornada.encuentros.all())
        orden_url = reverse(
            "torneos:reordenar_encuentros",
            args=[self.torneo.pk, jornada.pk],
        )

        respuesta = self.client.post(
            orden_url,
            {"orden_ids": f"{partidos[0].pk},{partidos[0].pk}"},
            follow=True,
        )

        self.assertContains(respuesta, "debe incluir cada partido")
        self.assertEqual(
            list(jornada.encuentros.values_list("pk", flat=True)),
            [partido.pk for partido in partidos],
        )

    def test_no_permite_equipo_repetido_en_jornada_historica(self):
        equipos = self.crear_equipos(4)
        self.client.force_login(self.administrador)
        respuesta = self.client.post(
            reverse("torneos:registrar_jornada_anterior", args=[self.torneo.pk]),
            {
                "fecha_programada": "2026-10-25",
                "form-TOTAL_FORMS": "2",
                "form-INITIAL_FORMS": "0",
                "form-MIN_NUM_FORMS": "2",
                "form-MAX_NUM_FORMS": "2",
                "form-0-equipo_local": equipos[0].pk,
                "form-0-equipo_visitante": equipos[1].pk,
                "form-1-equipo_local": equipos[0].pk,
                "form-1-equipo_visitante": equipos[2].pk,
            },
            follow=True,
        )

        self.assertContains(respuesta, "exactamente una vez")
        self.assertFalse(Jornada.objects.filter(torneo=self.torneo).exists())

    def test_reemplazar_ficticio_conserva_calendario_y_resultados(self):
        self.crear_equipos(11)
        ficticio = crear_equipo_ficticio(self.torneo)
        self.client.force_login(self.administrador)
        self.client.post(self.generar_url)
        jornada = Jornada.objects.get(torneo=self.torneo, numero=1)
        partido = jornada.encuentros.first()
        partido.goles_local = 2
        partido.goles_visitante = 0
        partido.save(update_fields=["goles_local", "goles_visitante"])
        total_partidos = Encuentro.objects.filter(jornada__torneo=self.torneo).count()

        respuesta = self.client.post(
            reverse(
                "torneos:equipos:reemplazar_ficticio",
                args=[self.torneo.pk, ficticio.pk],
            ),
            {"nombre": "Equipo real inscrito"},
        )

        self.assertRedirects(
            respuesta,
            reverse("torneos:equipos:lista", args=[self.torneo.pk]),
        )
        ficticio.refresh_from_db()
        partido.refresh_from_db()
        self.assertEqual(ficticio.nombre, "Equipo real inscrito")
        self.assertFalse(ficticio.es_ficticio)
        self.assertEqual((partido.goles_local, partido.goles_visitante), (2, 0))
        self.assertEqual(
            Encuentro.objects.filter(jornada__torneo=self.torneo).count(),
            total_partidos,
        )

    def test_no_genera_calendario_con_cantidad_impar(self):
        self.crear_equipos(3)
        self.client.force_login(self.administrador)

        respuesta = self.client.post(self.generar_url)

        self.assertRedirects(respuesta, self.url)
        self.assertFalse(Jornada.objects.filter(torneo=self.torneo).exists())
        self.assertContains(self.client.get(self.url), "cantidad par")
