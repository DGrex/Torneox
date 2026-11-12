# TorneoX

Sistema integral de gestión de torneos de fútbol (fútbol 5 a 11), con roles
de **Administrador** y **Dirigente de equipo**, inscripciones, arbitrajes,
multas y reglas de bonificación por fase.

## Stack

- Python 3 + Django 5.2 (LTS)
- SQLite en desarrollo → PostgreSQL en producción
- Tailwind CSS (vía CDN por ahora)
- Variables de entorno con `django-environ`

## Primeros pasos (local)

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # y completa DJANGO_SECRET_KEY
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Estructura de apps

| App | Responsabilidad |
|---|---|
| `usuarios` | Autenticación, modelo de usuario y roles |
| `equipos` | Registro de equipos participantes y sus dirigentes |
| `torneos` | Torneos, fases, calendario |
| `partidos` | Resultados, tarjetas, estadísticas |
| `finanzas` | Inscripciones, arbitrajes, multas |

## Seguridad

- `SECRET_KEY` y credenciales **solo** por variables de entorno (nunca en el código).
- `DEBUG=False` por defecto; se activa a propósito en `.env` local.
- Cookies de sesión y CSRF con `HttpOnly`; en producción además `Secure` y HSTS.
- Validadores de contraseña reforzados (mínimo 10 caracteres).

## Migración a PostgreSQL

Cuando se despliegue, basta con definir `DATABASE_URL` en el entorno de
producción (por ejemplo `postgres://usuario:password@host:5432/bd`); el
proyecto la detecta automáticamente sin cambiar código.

## Estado

El primer módulo funcional es la configuración de torneos. Los administradores
pueden crear torneos, definir cuántos equipos participarán y cuántos avanzan
desde la primera fase, además de establecer el máximo de jugadores por equipo.
Estos datos se pueden dejar pendientes al crear el torneo; la interfaz recuerda
completarlos antes de iniciar el campeonato, cerrar la fase y registrar
jugadores, respectivamente. También pueden habilitar una bonificación
opcional de 2 puntos para el primer lugar y 1 punto para el segundo. La fase
inicial está definida como todos contra todos, con participación de todos los
equipos inscritos.

Los administradores ya pueden registrar equipos por torneo y hasta tres
dirigentes por equipo, marcando uno como contacto prioritario. La gestión de
jugadores permite registrar cédula ecuatoriana, nombres y apellidos completos;
se impiden duplicados por cédula o nombre completo, y se respeta el máximo de
jugadores definido para el torneo. También se pueden editar equipos, datos de
contacto del dirigente prioritario y jugadores. La gestión de partidos, tabla
de posiciones y el cierre de fase (donde se aplicarán las bonificaciones) se
implementarán en sus respectivos módulos.

Desde el panel de cada torneo, el administrador puede generar una vez el
calendario de todos contra todos a una vuelta para los equipos registrados.
Con un número impar de equipos, cada jornada asigna un equipo libre; por
ejemplo, con 11 equipos se generan 11 jornadas, cinco partidos y un equipo
libre por jornada. La generación no asigna todavía fechas de calendario.
