# Issue #5: validación de servicios locales

Fecha: 13 de noviembre de 2026 (America/Bogota).
Rama: `chore/issue-5-docker-compose`, creada sobre `87b826f` de main,
que ya contiene los PR #9 y #10. El árbol inicial estaba limpio.

## Implementación y alcance

- `compose.yaml`: backend, frontend, PostgreSQL y Mailpit; healthchecks,
  dependencias saludables, políticas `unless-stopped` y volumen PostgreSQL.
- `backend/Dockerfile` y `.dockerignore`: Python 3.12.16 slim Bookworm,
  dependencias existentes y usuario sin privilegios; se excluyen entornos,
  cachés, SQLite y archivos de secretos del contexto de construcción.
- `frontend/Dockerfile` y `.dockerignore`: Node 22.23.5 LTS, `npm ci`, usuario
  node y exclusión de dependencias Windows/compilados/secretos del contexto.
- `backend/config/settings.py`: transporte SMTP configurable para Mailpit;
  consola por defecto fuera de Compose. No se añaden servicios de correo real.
- `frontend/vite.config.ts`: proxy `/api/` al backend y polling opcional para
  Windows/WSL; conserva comportamiento standalone y configuración Vitest.
- `.env.example`: puertos y explicación de configuración SMTP local.
- `docs/development/README.md`, `docker-compose.md` y este informe: instalación,
  operación sin pérdida de datos, pruebas y resultados.

PostgreSQL usa `postgres:17.12-bookworm`; Mailpit `axllent/mailpit:v1.33.1`.
Las versiones de imagen fueron verificadas en el registro oficial. Se fijan tags
de versión exacta, no digests inmutables. No se cambiaron versiones de paquetes
Python/npm, lockfile, workflow ni decisiones ADR/TD. No hay funcionalidades
comerciales ni implementación de autenticación nueva; las migraciones son las
incluidas por Django en el bootstrap existente.

## Entorno y comprobaciones realmente ejecutadas

Windows, Docker Engine 29.8.1, Docker Compose 5.5.1, contenedores Linux.
Docker Desktop estaba detenido: `docker desktop start` inició el motor y
`docker info` confirmó su disponibilidad.

| Comando | Resultado |
| --- | --- |
| `docker compose config` | Código 0; salida resuelta descartada para no imprimir credenciales. |
| `docker compose config --quiet` | Código 0 en la configuración final. |
| `docker compose build` | Código 0 para backend/frontend, incluida instalación real `npm ci`. |
| `docker compose up -d` | Código 0. |
| `docker compose up -d --wait --wait-timeout 90` | Código 0; cuatro servicios saludables. |
| `docker compose ps` | Cuatro servicios activos; backend 8000, frontend 5173, SMTP 1025 y web Mailpit 8025 publicados en 127.0.0.1; DB sin puerto publicado. |
| `docker compose exec -T backend python manage.py migrate --noinput` | Código 0; 18 migraciones estándar aplicadas en PostgreSQL. |
| `docker compose exec -T backend python manage.py check` | Código 0. |
| `docker compose exec -T backend python -m pytest -q` | Código 0; 1 prueba aprobada. |
| `docker compose exec -T backend python -m ruff check .` | Código 0. |
| `docker compose exec -T frontend npm run lint` | Código 0. |
| `docker compose exec -T frontend npm test` | Código 0; 1 prueba aprobada. |
| `docker compose exec -T frontend npm run build` | Código 0; TypeScript y Vite, 29 módulos. |
| `docker compose restart` seguido de `up -d --wait` | Código 0; los cuatro servicios vuelven a healthy. |

También se ejecutaron check/pytest/Ruff fuera de Docker con Python 3.12.10,
y lint/test/build con Node 22.23.5 del anfitrión: todos pasaron después de la
corrección de configuración de Vite descrita abajo.

## Evidencia de integración

- `pg_isready` pasa en el healthcheck. Además, Django abrió una conexión real,
  verificó `connection.vendor == 'postgresql'` y consultó `current_database()`
  y `version()`: `inventory_sales_dev`, PostgreSQL 17.12. No se usó SQLite.
- HTTP desde el anfitrión: `/health/` en 8000 responde 200 y `{"status":"ok"}`.
- El HTML de Vite y los módulos transformados `/src/main.tsx` y `/src/App.tsx`
  responden 200; se verificaron `createRoot` y el contenido de la aplicación.
- `/api/v1/` a través de 5173 devuelve el 404 de Django, lo que comprueba el
  proxy sin inventar endpoints comerciales. Se preserva el Host del navegador.
- Mailpit web responde 200. `send_mail` de Django entregó un correo con remitente
  y destinatario reservados `.test`; la API `/api/v1/messages` confirmó el asunto
  `Issue 5 SMTP smoke`. No hubo entrega a servicios externos.
- Se conectó un WebSocket con el protocolo/token HMR de Vite; una edición
  temporal del CSS montado desde Windows generó un mensaje de actualización
  para `style.css`. Se restauró el archivo original byte por byte.
- Persistencia: se creó una tabla de prueba con un marcador, se recreó únicamente
  `db` con `docker compose up -d --force-recreate db` y se esperó disponibilidad.
  Cambió el ID del contenedor; el marcador y los 18 registros de migraciones
  seguían presentes. Se eliminó únicamente la tabla de prueba creada por esta
  validación. No se borró el volumen ni datos anteriores.

La inspección visual automatizada no pudo ejecutarse: el host de acceso del
navegador de computer-use no estaba disponible. No se presenta como aprobada.
La carga HTTP, transformación de módulos y WebSocket HMR sí se verificaron
realmente; la revisión visual manual sigue disponible en las URLs locales.

## Problemas detectados y corregidos

1. La primera configuración de Vite accedía a `globalThis.process`, sin tipos de
   Node en este proyecto; TypeScript devolvió TS7017. Se sustituyó por `loadEnv`
   de Vite para variables `DEV_*`, sin nuevas dependencias. Lint, test y build
   se repitieron con éxito.
2. Docker Engine 29 no publicó puertos de servicios conectados únicamente a una
   red `internal`. Aunque los healthchecks internos pasaban, HTTP desde Windows
   fallaba y `NetworkSettings.Ports` estaba vacío. Se añadió `host_access` para
   los tres servicios con puertos de anfitrión, y se recrearon. PostgreSQL sigue
   únicamente en la red interna. Los cuatro puertos publicados quedaron ligados
   a 127.0.0.1 y las comprobaciones HTTP/SMTP posteriores pasaron.
3. `npm ci` informa las 10 alertas moderadas de desarrollo ya documentadas en
   Issue #4. No se ocultaron ni se forzaron actualizaciones fuera del alcance.

## Seguridad, datos y límites

Se generó `.env` local ignorado con valores aleatorios exclusivos de desarrollo;
no se imprimieron ni se añadieron al índice. El `.gitignore` integrado ya cubre
secretos y temporales: no fue necesario cambiarlo. El frontend recibe solo el
destino del proxy y la opción de polling, nunca credenciales de Django/PostgreSQL.
No se añadió CORS permisivo, excepciones CSRF, hosts comodín ni autenticación SMTP
real. La red interna y la ausencia de puerto de DB restringen su exposición;
backend/frontend/Mailpit tienen salida por su bridge de acceso. Mailpit no tiene
relay/forwarding configurado.

Las pruebas existentes son smoke tests; no certifican seguridad de producción,
aislamiento multiempresa ni cobertura funcional. PostgreSQL usa el usuario de
inicialización de la imagen, apropiado solo para este entorno local. Las versiones
fijadas requieren actualizaciones de mantenimiento posteriores. El procedimiento
operativo explica cómo reconstruir dependencias y conservar los datos sin usar
`down --volumes`.

## Revisión de Git

`git diff --check` y `git diff --cached --check` pasaron. Se revisaron exactamente
11 archivos del Issue #5. El escaneo del índice no encontró marcadores de
conflicto, patrones de claves ni ninguno de los valores aleatorios de `.env`.
Los ADR, TD, documentos de arquitectura, dependencias y workflow permanecen
intactos respecto a main. Los cuatro servicios quedaron activos y saludables;
se pueden detener sin borrar datos con `docker compose stop`.

## Conceptos para una entrevista

- Una imagen empaqueta runtime/dependencias; el contenedor ejecuta esa imagen.
  Los bind mounts permiten editar código, pero node_modules necesita aislamiento
  por sistema operativo y no debe reemplazarse con la instalación de Windows.
- Un volumen nombrado vive independientemente del contenedor; recrear PostgreSQL
  no debe destruir sus datos. Cambiar variables iniciales no cambia credenciales
  de una base ya creada.
- `depends_on` con healthcheck espera disponibilidad, mientras una dependencia
  simplemente iniciada puede no estar lista. La salud HTTP no certifica DB ni
  migraciones: se verificaron por separado.
- `127.0.0.1` en el host y `0.0.0.0` dentro del contenedor cumplen funciones
  distintas. Docker DNS resuelve nombres de servicio dentro de sus redes.
- El proxy de Vite permite solicitudes same-origin al backend; HMR usa WebSocket.
  SMTP de captura permite comprobar integración sin enviar correo a personas.
- `npm ci` y el lockfile fijan resoluciones npm; los tags de imagen fijan versiones
  legibles, mientras un digest fija contenido. Ninguno sustituye revisar parches.

La publicación se realiza como PR en borrador hacia main, relacionado con #5.
Los resultados de GitHub Actions se consultan después de publicar; las pruebas
Docker de este informe son locales y no se atribuyen al workflow del Issue #4.
