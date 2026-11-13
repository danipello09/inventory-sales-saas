# Issue #6: GitHub Actions quality checks

Fecha: 13 de noviembre de 2026 (America/Bogota).
Rama: `chore/issue-6-github-actions`.
Base confirmada después de `git fetch origin`:
`a7c390ecbc61c4245566208a2a6c147cf795063f`, idéntica a `origin/main`.
Árbol inicial limpio. Issue #6 consultado en GitHub; se revisaron workflow,
Dockerfiles, Compose, dependencias, pruebas, informes #4/#5, ADR y contratos TD.

## Diagnóstico y cambios

El workflow anterior ya ejecutaba check/pytest/Ruff y lint/test/build, con caché
pip y permisos de lectura. Faltaban PostgreSQL real, Compose, caché npm, timeouts,
cancelación de PR redundantes, acciones inmutables y auditoría con umbrales.
El trigger push seguía ligado a la rama histórica del Issue #4.

Se conserva el mismo archivo de workflow y los nombres visibles de los dos checks
existentes. Ahora hay cinco jobs independientes: `backend-quality`,
`frontend-quality`, `postgres-integration`, `compose-validation`, `dependency-audit`.
Se ejecutan en PR a main, push a main y dispatch manual. Ver
[guía CI](ci.md) para comandos exactos, logs, reproducción y política de seguridad.

Archivos: workflow existente, `backend/tests/test_database.py`, índice de
desarrollo, guía `ci.md` y este informe. No se modifican dependencias, lockfile,
Compose, Dockerfiles, settings, ADR/TD ni funcionalidad comercial.
La nueva prueba comprueba SQL real, proveedor esperado y migración aplicada en la
base temporal de pytest; resuelve una carencia real del smoke HTTP anterior,
que no accedía a ninguna base de datos.

## Validación local realmente ejecutada

Docker Desktop se inició con `docker desktop start`; Engine 29.8.1 disponible.
Backend: entorno existente Python 3.12.10 en Windows. Frontend: contenedor efímero
`node:22.23.5-bookworm-slim`, Node 22.23.5/npm 10.9.9, copia en `/work` y montaje
del repositorio solo lectura; no sustituye node_modules ni genera dist en Windows.
El Node predeterminado del anfitrión es 25.2.1; no se usó para estos checks.

| Comando o comprobación | Resultado real |
| --- | --- |
| `git status --short`, rama, fetch, comparación HEAD/origin/main | Limpio, rama y base correctas antes de editar. |
| `python -m pip install -r requirements.txt` | 0; dependencias existentes satisfechas. |
| `python manage.py check` con SQLite | 0; sin problemas, 0 controles silenciados. |
| `python -m ruff check .` | 0. |
| `python -m pytest -q` con SQLite y proveedor esperado | 0; 2 pruebas aprobadas. |
| PostgreSQL 17.12, contenedor efímero, puerto aleatorio en 127.0.0.1 | Saludable; sin volumen local compartido. |
| `python manage.py migrate --noinput` con PostgreSQL | 0; 18 migraciones estándar aplicadas. |
| `python manage.py check` con PostgreSQL | 0; sin problemas, 0 controles silenciados. |
| ensure_connection + assert vendor + `SELECT current_database(), version()` | 0; `postgresql`, `inventory_ci`, PostgreSQL 17.12. |
| `python manage.py makemigrations --check --dry-run` | 0; No changes detected. |
| `python -m pytest -q` con PostgreSQL y proveedor esperado | 0; 2 pruebas aprobadas; pytest crea/migra/elimina su base de prueba. |
| `npm ci` con Node 22 | 0; 194 paquetes instalados, 9 alertas moderadas visibles. |
| `npm run lint` | 0. |
| `npm test` | 0; 1 archivo, 1 prueba aprobada. |
| `npm run build` | 0; TypeScript y Vite, 29 módulos. |
| `npm audit --omit=dev --audit-level=low` | 0; ninguna vulnerabilidad de producción. |
| `npm audit --audit-level=high` | 0 por umbral; 9 moderadas de desarrollo, ninguna alta/crítica. No significa cero vulnerabilidades. |
| `docker compose --env-file .env.example config --quiet` con variables ficticias explícitas | 0; no se imprime configuración resuelta. |
| Comparación de `config --services` | 0; backend, db, frontend, mailpit. |
| `rhysd/actionlint:1.7.7` sobre workflow | 0; sin diagnósticos. |

El contenedor PostgreSQL y su volumen anónimo se eliminaron en `finally`, dirigido
solo al nombre único creado para esta prueba. El contenedor frontend usó `--rm`.
No se levantó ni destruyó el proyecto Compose local ni su volumen persistente.

## PostgreSQL, Docker y seguridad en CI

El service container espera healthcheck antes de pasos de integración. Django debe
abrir una conexión y demostrar proveedor PostgreSQL antes de pytest. El test de
infraestructura también comprueba el proveedor en la base de prueba y la migración
de sesiones. No se confunde un check estático con acceso a PostgreSQL.
Actions limpia el servicio y sus recursos al finalizar; Compose config no crea
contenedores. No se levantan los cuatro servicios en CI: se conserva el smoke
integrado local documentado en #5 y se evita repetir builds/instalaciones en cada
PR. Esto deja fuera de este CI la validación de Dockerfiles, SMTP, HMR y los
healthchecks del stack completo; la guía explica cuándo repetirla localmente.

Permisos `contents: read`, checkout sin credenciales persistentes, acciones fijadas
por SHA, timeouts y cancelación de ejecuciones PR obsoletas. No hay
`pull_request_target`, `continue-on-error`, tokens personales, secretos reales,
despliegues ni cambios de protección de ramas. Los valores `ci-only-*` son públicos,
ficticios y exclusivos del servicio desechable. No se relajan controles de Django.
Los SHA de actions se contrastaron con tags reales mediante `git ls-remote`.

## Vulnerabilidades y límites

Permanece deuda transitiva de minimatch, GHSA-g3hv-75wg-m249, en herramientas de
desarrollo. La auditoría Linux actual reporta 9 moderadas frente a las 10
históricas; no se alteraron manifiestos ni lockfile y no se afirma haberla resuelto.
Producción: cualquier severidad falla. Árbol completo: alta/crítica falla;
baja/moderada de desarrollo permanece visible y requiere revisión mensual y en
PR de dependencias. No hay auditoría Python automatizada ni lock transitivo Python
completo. Las pruebas son smoke de infraestructura; no certifican negocio,
aislamiento multiempresa ni preparación para producción.

## GitHub remoto y revisión final

Pendiente de registrar después del primer commit/push y de crear el PR borrador.
La validación actionlint anterior es local y no se presenta como ejecución remota.
No se hará merge ni se cerrará el Issue #6.
