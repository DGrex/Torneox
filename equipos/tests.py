from datetime import date

from django.test import TestCase

from django.urls import reverse

from torneos.models import Encuentro, Jornada, Torneo
from torneos.services import (
    crear_calendario_todos_contra_todos,
    registrar_jornada_historica,
)
from usuarios.models import Usuario

from .models import DirigenteEquipo, Equipo, Jugador


class RegistroEquiposTests(TestCase):
    def setUp(self):
        self.administrador = Usuario.objects.create_user(
            username="admin-equipos",
            password="ClaveSegura123!",
            rol=Usuario.Rol.ADMINISTRADOR,
        )
        self.dirigente_usuario = Usuario.objects.create_user(
            username="dirigente-usuario",
            password="ClaveSegura123!",
            rol=Usuario.Rol.DIRIGENTE,
        )
        self.torneo = Torneo.objects.create(
            nombre="Campeonato de Prueba",
            equipos_participantes=2,
            jugadores_maximos_por_equipo=2,
        )
        self.url = reverse("torneos:equipos:lista", args=[self.torneo.pk])
        self.equipo = Equipo.objects.create(
            torneo=self.torneo,
            nombre="Deportivo de Prueba",
        )
        self.jugadores_url = reverse(
            "torneos:equipos:jugadores",
            args=[self.torneo.pk, self.equipo.pk],
        )

    def test_administrador_registra_equipo_y_hasta_tres_dirigentes(self):
        self.client.force_login(self.administrador)

        respuesta = self.client.post(
            self.url,
            {
                "nombre": "Deportivo Norte",
                "dirigente_1": "Ana Pérez",
                "dirigente_2": "Luis Gómez",
                "dirigente_3": "Eva Ruiz",
                "dirigente_prioritario": "2",
                "telefono_prioritario": "0991234567",
                "correo_prioritario": "luis@example.com",
            },
        )

        self.assertRedirects(respuesta, self.url)
        equipo = Equipo.objects.get(nombre="Deportivo Norte")
        dirigentes = list(equipo.dirigentes.order_by("nombre"))
        self.assertEqual(len(dirigentes), 3)
        self.assertEqual(
            [dirigente.nombre for dirigente in dirigentes if dirigente.es_prioritario],
            ["Luis Gómez"],
        )
        dirigente_prioritario = next(
            dirigente for dirigente in dirigentes if dirigente.es_prioritario
        )
        self.assertEqual(dirigente_prioritario.telefono, "0991234567")
        self.assertEqual(dirigente_prioritario.correo_electronico, "luis@example.com")

    def test_equipo_se_puede_registrar_con_un_solo_dirigente(self):
        self.client.force_login(self.administrador)

        respuesta = self.client.post(
            self.url,
            {
                "nombre": "Unión Sur",
                "dirigente_1": "María López",
                "dirigente_prioritario": "1",
                "telefono_prioritario": "0987654321",
                "correo_prioritario": "maria@example.com",
            },
        )

        self.assertRedirects(respuesta, self.url)
        self.assertEqual(
            DirigenteEquipo.objects.filter(equipo__nombre="Unión Sur").count(),
            1,
        )

    def test_no_permite_priorizar_un_dirigente_sin_nombre(self):
        self.client.force_login(self.administrador)

        respuesta = self.client.post(
            self.url,
            {
                "nombre": "Equipo Inválido",
                "dirigente_1": "Ana Pérez",
                "dirigente_prioritario": "2",
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Equipo.objects.filter(nombre="Equipo Inválido").exists())
        self.assertContains(respuesta, "debe tener un nombre")

    def test_no_permite_superar_el_maximo_de_participantes(self):
        Equipo.objects.create(torneo=self.torneo, nombre="Equipo Uno")
        Equipo.objects.create(torneo=self.torneo, nombre="Equipo Dos")
        self.client.force_login(self.administrador)

        respuesta = self.client.post(
            self.url,
            {
                "nombre": "Equipo Tres",
                "dirigente_1": "Ana Pérez",
                "dirigente_prioritario": "1",
                "telefono_prioritario": "0987654321",
                "correo_prioritario": "ana@example.com",
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Se alcanzó el límite de participantes")
        self.assertFalse(Equipo.objects.filter(nombre="Equipo Tres").exists())

    def test_dirigente_no_administrador_no_puede_gestionar_equipos(self):
        self.client.force_login(self.dirigente_usuario)

        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 403)

    def test_administrador_puede_editar_jugador_con_sus_mismos_datos(self):
        jugador = Jugador.objects.create(
            equipo=self.equipo,
            cedula="1710034065",
            nombres="María Elena",
            apellidos="Pérez López",
        )
        editar_url = reverse(
            "torneos:equipos:editar_jugador",
            args=[self.torneo.pk, self.equipo.pk, jugador.pk],
        )
        self.client.force_login(self.administrador)

        respuesta = self.client.post(
            editar_url,
            {
                "cedula": "1710034065",
                "nombres": "María Elena",
                "apellidos": "Pérez López",
            },
        )

        self.assertRedirects(respuesta, self.jugadores_url)
        jugador.refresh_from_db()
        self.assertEqual(jugador.cedula, "1710034065")
        self.assertEqual(jugador.nombre_completo, "María Elena Pérez López")

    def test_editar_jugador_rechaza_duplicado_de_otro_jugador(self):
        jugador = Jugador.objects.create(
            equipo=self.equipo,
            cedula="1710034065",
            nombres="María Elena",
            apellidos="Pérez López",
        )
        Jugador.objects.create(
            equipo=self.equipo,
            cedula="1710034073",
            nombres="Carlos",
            apellidos="García",
        )
        editar_url = reverse(
            "torneos:equipos:editar_jugador",
            args=[self.torneo.pk, self.equipo.pk, jugador.pk],
        )
        self.client.force_login(self.administrador)

        respuesta = self.client.post(
            editar_url,
            {
                "cedula": "1710034073",
                "nombres": "María Elena",
                "apellidos": "Pérez López",
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Ya existe un jugador registrado con esta cédula.")
        jugador.refresh_from_db()
        self.assertEqual(jugador.cedula, "1710034065")

    def test_no_permite_repetir_nombre_de_equipo_en_el_mismo_torneo(self):
        Equipo.objects.create(torneo=self.torneo, nombre="Deportivo Norte")
        self.client.force_login(self.administrador)

        respuesta = self.client.post(
            self.url,
            {
                "nombre": "Deportivo Norte",
                "dirigente_1": "Ana Pérez",
                "dirigente_prioritario": "1",
                "telefono_prioritario": "0987654321",
                "correo_prioritario": "ana@example.com",
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            Equipo.objects.filter(torneo=self.torneo, nombre="Deportivo Norte").count(),
            1,
        )

    def test_permite_agregar_equipo_despues_de_generar_calendario(self):
        self.torneo.equipos_participantes = 4
        self.torneo.save(update_fields=["equipos_participantes"])
        Equipo.objects.create(torneo=self.torneo, nombre="Equipo de Calendario")
        crear_calendario_todos_contra_todos(self.torneo)
        self.client.force_login(self.administrador)

        respuesta = self.client.post(
            self.url,
            {
                "nombre": "Equipo Posterior",
                "dirigente_1": "Ana Pérez",
                "dirigente_prioritario": "1",
                "telefono_prioritario": "0987654321",
                "correo_prioritario": "ana@example.com",
            },
        )

        self.assertRedirects(respuesta, self.url)
        equipo_nuevo = Equipo.objects.get(nombre="Equipo Posterior")
        equipo_ficticio = Equipo.objects.get(torneo=self.torneo, es_ficticio=True)
        self.assertEqual(Equipo.objects.filter(torneo=self.torneo).count(), 4)
        self.assertEqual(
            equipo_nuevo.encuentros_como_local.count()
            + equipo_nuevo.encuentros_como_visitante.count(),
            3,
        )
        self.assertEqual(
            equipo_ficticio.encuentros_como_local.count()
            + equipo_ficticio.encuentros_como_visitante.count(),
            3,
        )
        for jornada in self.torneo.jornadas.all():
            ordenes = list(jornada.encuentros.values_list("orden", flat=True))
            self.assertEqual(ordenes, list(range(len(ordenes))))

    def test_no_permite_agregar_equipo_despues_de_registrar_fecha_historica(self):
        equipos_adicionales = [
            Equipo.objects.create(torneo=self.torneo, nombre=f"Equipo previo {numero}")
            for numero in range(2, 5)
        ]
        self.torneo.equipos_participantes = 6
        self.torneo.save(update_fields=["equipos_participantes"])
        registrar_jornada_historica(
            torneo=self.torneo,
            fecha_programada=date(2026, 10, 25),
            partidos=[
                {
                    "equipo_local": self.equipo,
                    "goles_local": 1,
                    "equipo_visitante": equipos_adicionales[0],
                    "goles_visitante": 0,
                },
                {
                    "equipo_local": equipos_adicionales[1],
                    "goles_local": 2,
                    "equipo_visitante": equipos_adicionales[2],
                    "goles_visitante": 0,
                },
            ],
        )
        self.client.force_login(self.administrador)

        respuesta = self.client.post(
            self.url,
            {
                "nombre": "Equipo Posterior",
                "dirigente_1": "Ana Pérez",
                "dirigente_prioritario": "1",
                "telefono_prioritario": "0987654321",
                "correo_prioritario": "ana@example.com",
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "jornadas históricas registradas")
        self.assertFalse(
            Equipo.objects.filter(torneo=self.torneo, nombre="Equipo Posterior").exists()
        )
        self.assertEqual(Encuentro.objects.filter(jornada__torneo=self.torneo).count(), 2)

    def test_administrador_puede_editar_equipo_y_contacto_prioritario(self):
        dirigente = DirigenteEquipo.objects.create(
            equipo=self.equipo,
            nombre="Ana Pérez",
            telefono="0990000000",
            correo_electronico="ana@old.example",
            es_prioritario=True,
        )
        editar_url = reverse(
            "torneos:equipos:editar",
            args=[self.torneo.pk, self.equipo.pk],
        )
        self.client.force_login(self.administrador)

        respuesta = self.client.post(
            editar_url,
            {
                "nombre": "Deportivo Actualizado",
                "dirigente_1": "Ana Pérez Actualizada",
                "dirigente_prioritario": "1",
                "telefono_prioritario": "0991234567",
                "correo_prioritario": "ana@example.com",
            },
        )

        self.assertRedirects(respuesta, self.url)
        self.equipo.refresh_from_db()
        dirigente.refresh_from_db()
        self.assertEqual(self.equipo.nombre, "Deportivo Actualizado")
        self.assertEqual(dirigente.nombre, "Ana Pérez Actualizada")
        self.assertEqual(dirigente.telefono, "0991234567")
        self.assertEqual(dirigente.correo_electronico, "ana@example.com")

    def test_administrador_puede_eliminar_equipo_y_datos_relacionados(self):
        equipo = Equipo.objects.create(torneo=self.torneo, nombre="Equipo para eliminar")
        jugador = Jugador.objects.create(
            equipo=equipo,
            cedula="1710034065",
            nombres="María Elena",
            apellidos="Pérez López",
        )
        url = reverse(
            "torneos:equipos:eliminar",
            args=[self.torneo.pk, equipo.pk],
        )
        self.client.force_login(self.administrador)

        confirmacion = self.client.get(url)
        self.assertEqual(confirmacion.status_code, 200)
        self.assertTrue(Equipo.objects.filter(pk=equipo.pk).exists())
        self.assertContains(confirmacion, "jugadores")

        respuesta = self.client.post(url)

        self.assertRedirects(respuesta, self.url)
        self.assertFalse(Equipo.objects.filter(pk=equipo.pk).exists())
        self.assertFalse(Jugador.objects.filter(pk=jugador.pk).exists())

    def test_no_permite_eliminar_equipo_con_partido_jugado(self):
        otro_equipo = Equipo.objects.create(torneo=self.torneo, nombre="Rival")
        jornada = Jornada.objects.create(torneo=self.torneo, numero=1)
        partido = Encuentro.objects.create(
            jornada=jornada,
            equipo_local=self.equipo,
            equipo_visitante=otro_equipo,
            goles_local=0,
            goles_visitante=0,
        )
        url = reverse(
            "torneos:equipos:eliminar",
            args=[self.torneo.pk, self.equipo.pk],
        )
        self.client.force_login(self.administrador)

        respuesta = self.client.post(url)

        self.assertRedirects(respuesta, self.url)
        self.assertTrue(Equipo.objects.filter(pk=self.equipo.pk).exists())
        self.assertTrue(Encuentro.objects.filter(pk=partido.pk).exists())

    def test_eliminar_jugador_borra_solo_el_registro_seleccionado(self):
        jugador = Jugador.objects.create(
            equipo=self.equipo,
            cedula="1710034065",
            nombres="María Elena",
            apellidos="Pérez López",
        )
        url = reverse(
            "torneos:equipos:eliminar_jugador",
            args=[self.torneo.pk, self.equipo.pk, jugador.pk],
        )
        self.client.force_login(self.administrador)

        confirmacion = self.client.get(url)
        self.assertEqual(confirmacion.status_code, 200)
        respuesta = self.client.post(url)

        self.assertRedirects(respuesta, self.jugadores_url)
        self.assertFalse(Jugador.objects.filter(pk=jugador.pk).exists())
        self.assertTrue(Equipo.objects.filter(pk=self.equipo.pk).exists())

    def test_editar_equipo_muestra_contacto_prioritario_actual(self):
        DirigenteEquipo.objects.create(
            equipo=self.equipo,
            nombre="Ana Pérez",
            telefono="0990000000",
            correo_electronico="ana@example.com",
            es_prioritario=True,
        )
        editar_url = reverse(
            "torneos:equipos:editar",
            args=[self.torneo.pk, self.equipo.pk],
        )
        self.client.force_login(self.administrador)

        respuesta = self.client.get(editar_url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'value="0990000000"')
        self.assertContains(respuesta, 'value="ana@example.com"')

    def test_registra_jugador_con_cedula_ecuatoriana_valida(self):
        self.client.force_login(self.administrador)

        respuesta = self.client.post(
            self.jugadores_url,
            {
                "registrar_jugador": "1",
                "cedula": "1710034065",
                "nombres": "María Elena",
                "apellidos": "Pérez López",
            },
        )

        self.assertRedirects(respuesta, self.jugadores_url)
        jugador = Jugador.objects.get(cedula="1710034065")
        self.assertEqual(jugador.equipo, self.equipo)
        self.assertEqual(jugador.nombre_completo, "María Elena Pérez López")

    def test_pantalla_de_jugadores_muestra_formulario_y_regla_del_maximo(self):
        self.client.force_login(self.administrador)

        respuesta = self.client.get(self.jugadores_url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Agregar jugador")
        self.assertContains(respuesta, "Nombres")
        self.assertContains(respuesta, "Apellidos")
        self.assertContains(respuesta, "de 2")

    def test_rechaza_cedula_ecuatoriana_invalida(self):
        self.client.force_login(self.administrador)

        respuesta = self.client.post(
            self.jugadores_url,
            {
                "registrar_jugador": "1",
                "cedula": "1710034064",
                "nombres": "María Elena",
                "apellidos": "Pérez López",
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Jugador.objects.filter(cedula="1710034064").exists())
        self.assertContains(respuesta, "La cédula ecuatoriana no es válida.")

    def test_rechaza_cedula_duplicada_en_otro_equipo(self):
        otro_equipo = Equipo.objects.create(
            torneo=self.torneo,
            nombre="Otro Equipo",
        )
        Jugador.objects.create(
            equipo=otro_equipo,
            cedula="1710034065",
            nombres="Carlos",
            apellidos="García",
        )
        self.client.force_login(self.administrador)

        respuesta = self.client.post(
            self.jugadores_url,
            {
                "registrar_jugador": "1",
                "cedula": "1710034065",
                "nombres": "Otro Nombre",
                "apellidos": "Otro Apellido",
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Ya existe un jugador registrado con esta cédula.")
        self.assertEqual(Jugador.objects.filter(cedula="1710034065").count(), 1)

    def test_rechaza_nombre_completo_duplicado_ignorando_mayusculas_y_acentos(self):
        Jugador.objects.create(
            equipo=self.equipo,
            cedula="1710034065",
            nombres="José Luis",
            apellidos="Pérez Mora",
        )
        self.client.force_login(self.administrador)

        respuesta = self.client.post(
            self.jugadores_url,
            {
                "registrar_jugador": "1",
                "cedula": "1710034073",
                "nombres": "JOSE LUIS",
                "apellidos": "Perez Mora",
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(
            respuesta,
            "Ya existe un jugador registrado con estos nombres y apellidos.",
        )
        self.assertEqual(Jugador.objects.count(), 1)

    def test_no_permite_superar_maximo_de_jugadores_del_torneo(self):
        Jugador.objects.create(
            equipo=self.equipo,
            cedula="1710034065",
            nombres="Carlos",
            apellidos="García",
        )
        Jugador.objects.create(
            equipo=self.equipo,
            cedula="1710034073",
            nombres="Ana",
            apellidos="López",
        )
        self.client.force_login(self.administrador)

        respuesta = self.client.post(
            self.jugadores_url,
            {
                "registrar_jugador": "1",
                "cedula": "1710034081",
                "nombres": "Luis",
                "apellidos": "Vera",
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "alcanzó el máximo de 2 jugadores")
        self.assertEqual(Jugador.objects.filter(equipo=self.equipo).count(), 2)

    def test_solo_administradores_pueden_gestionar_jugadores(self):
        self.client.force_login(self.dirigente_usuario)

        respuesta = self.client.get(self.jugadores_url)

        self.assertEqual(respuesta.status_code, 403)
