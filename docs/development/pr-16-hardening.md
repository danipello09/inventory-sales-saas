# PR #16 — informe de endurecimiento final

Fecha: 13 de noviembre de 2026 (America/Bogota).
Rama: `feat/phase-3-identity-organizations`.
Revisión atendida: [COMMENT de GitHub](https://github.com/danipello09/inventory-sales-saas/pull/16#pullrequestreview-5900505530)
sobre `58125ea`. No constituye aprobación para merge ni exposición pública.

## Estado comprobado antes de editar

El worktree estaba limpio y HEAD coincidía con origin/feat/phase-3-identity-organizations.
Se ejecutó git fetch origin y se revisó el diff contra main, que avanzó a
`efa2602` e incluye onboarding #13, revisión de infraestructura #14 y diseño #15.
Se leyó el diseño integrado y la revisión del PR. Se incorporaron esos commits
solo a la rama de trabajo, conservando historial; main no se modifica y el PR no
se fusiona. No se descartaron cambios ni se usó force push.

## Hallazgos atendidos

1. **Cutover operativo:** README, contribuciones, guías de desarrollo/Docker y
   backend apuntan al [procedimiento nuevo](identity-cutover.md). No basta cambiar
   credenciales o usar el proyecto Compose predeterminado: el nuevo helper genera
   otro proyecto y verifica un volumen nombrado inexistente antes de crearlo.
   Fija compose.yaml/env/proyecto en cada invocación, inspecciona label y montaje
   real, usa puertos distintos solo en loopback y migra únicamente la base nueva.
2. **Protección legacy:** el guard y las migraciones existentes no se modificaron.
   Se volvió a construir un esquema auth.User antiguo en PostgreSQL desechable y
   se comprobó su rechazo antes de escrituras, conservando tablas/historial/marcador.
   La conversión de usuarios/datos originales continúa fuera de alcance.
3. **Cobertura concreta:** se añadieron 49 casos para entradas/CSRF/media type y
   reutilización/invalidez de sesiones, más cuatro casos exclusivos de PostgreSQL
   para concurrencia. No se sustituyó implementación por respuestas simuladas.
4. **Estado documental:** #13/#14/#15 figuran como integrados en guías actuales.
   Los informes/notas anteriores se etiquetan explícitamente como evidencia
   histórica, sin atribuir sus resultados al nuevo HEAD.
5. **Exposición pública:** [PUBLIC-001–004](identity-public-exposure.md) son tareas
   OPEN con propietario y evidencia de aceptación definida: rate limiting,
   verificación de email, recuperación y configuración/operación de producción.
   No se implementan esos controles ni funcionalidades comerciales en este cambio.

La revisión y las regresiones no demostraron un bypass de CSRF o acceso cruzado
en los endpoints actuales. Este cambio fortalece la evidencia y la seguridad del
arranque; no inventa una vulnerabilidad corregida ni cambia decisiones ADR/TD.

## Nuevas pruebas

`backend/tests/test_identity_inputs.py` envía JSON truncado, listas vacías/no vacías,
string, null, boolean y número a registro/login/logout/PATCH organización. Exige
400 controlado, sin creación/cambio de datos ni pérdida de sesión válida.
Los cuatro endpoints se prueban sin CSRF, con token distinto y Origin hostil,
y con contenido no JSON aunque haya CSRF válido. Otra prueba reutiliza una sesión
desde otro cliente y comprueba que logout invalida todas sus copias.

`backend/tests/test_identity_concurrency.py` usa transacciones confirmadas,
conexiones independientes y peticiones reales a las vistas en threads. Dos
registros simultáneos del mismo email (variando mayúsculas) deben producir solo
201 y 409, con un usuario/organización/membresía completos y ninguna sesión para
el perdedor. Tres escenarios mantienen un bloqueo real mientras revocan ADMIN,
desactivan membresía o suspenden organización. Se observa `pg_stat_activity` para
demostrar que la petición espera el lock; al liberar/confirmar debe responder 403
y no cambiar el nombre ni la otra organización. Hay límites de espera/SQL para
evitar bloqueos indefinidos. SQLite omite expresamente esos cuatro casos porque
no ofrece esos bloqueos PostgreSQL; no se declaran aprobados en SQLite.

## Validaciones realmente ejecutadas

Entorno local: Python 3.12.10, Django 5.2.8, PostgreSQL 17.12 desechable,
Docker Engine 29.8.1 y Compose 5.5.1. No se usó la base original.

| Comando/comprobación | Resultado real |
| --- | --- |
| `python manage.py check` desde backend | 0, sin problemas ni controles silenciados. |
| `python -m ruff check .` desde backend | 0. |
| `python manage.py makemigrations --check --dry-run` | 0; No changes detected. |
| `python -m pytest -q --tb=short` con SQLite | **101 passed, 4 skipped en 56.34 s**; omisiones exclusivas de PostgreSQL. |
| Python del venv + `scripts/verify_identity_database.py` | 0; PostgreSQL nuevo, rechazo legacy, migración nueva/idempotente, check/Ruff/drift y HTTP real. |
| pytest en ese PostgreSQL | **105 passed en 57.81 s**, sin omisiones. |
| Migrate contra esquema antiguo propio | Exit 1 esperado, mensaje Legacy auth.User; sin cambios en tablas/historial/marcador. |
| Migración fresh e idempotencia | 20 migraciones, UUID user, sin auth_user; repetición sin pendientes. |
| Python + `scripts/start_identity_sandbox.py --verify` | 0; proyecto y volumen nuevos verificados, cuatro servicios healthy y migración fresh. |
| HTTP después de Compose up | Dos registros 201 con CSRF; sin CSRF 403; rename ADMIN 200; STAFF PATCH 403; ID inyectado 400; ruta de otra org 404 y datos de otra org intactos. |
| Reinicio del backend nuevo | Sesión y organización persisten; logout 204 invalida copia de sesión (401), sin afectar al otro usuario ni al STAFF. |
| Modo normal del helper y prefijo del manifest | 0; nuevo sandbox retenido, stop/start --wait y health 200; al acabar la prueba solo se eliminó ese proyecto/volumen recién creado. |
| `docker compose ... config --quiet` | 0, con env nuevo explícito, sin imprimir valores resueltos. |
| Ruff del helper, enlaces, sintaxis de bloques y revisión de secretos/diff | Se ejecutan antes del commit; los resultados finales se incluyen en el PR junto con CI del HEAD. |

Evidencia estructurada sanitizada:
[PostgreSQL](evidence/pr-16-postgres-results.json),
[Compose/HTTP](evidence/pr-16-compose-results.json) y
[modo normal/lifecycle](evidence/pr-16-lifecycle-results.json).
No incluyen credenciales ni rutas personales. Los env/manifest/logs privados
permanecen fuera del repo. El primer intento del verificador Compose trató el
404 HTML normal de Django como JSON; se corrigió el verificador y se repitió con
otro proyecto nuevo hasta completar el recorrido. Una invocación de pytest desde
la raíz no encontró settings; se corrigió el directorio a backend y se ejecutó
la suite completa anterior. Ningún intento fallido se presenta como aprobado.

## Seguridad, límites y estado de entrega

Los proyectos de prueba se limpiaron por sus nombres nuevos y exclusivos. No se
conectó, borró ni recreó el volumen original, ni se ejecutó migrate/--fake sobre él.
Los cuatro contenedores originales siguieron healthy. No hay cambios en workflow,
dependencias, guard, migraciones antiguas ni decisiones arquitectónicas.

La evidencia prueba escenarios concretos, no todas las intercalaciones de
concurrencia ni módulos futuros. El helper es para desarrollo con DEBUG=true
en HTTP local; no es un despliegue de producción. PUBLIC-001–004 y el plan de
conversión legacy siguen abiertos. El baseline previo de npm incluye nueve
moderadas de desarrollo y cero de producción; la auditoría del nuevo HEAD se
consulta en CI. No se añade auditoría Python ni lock transitivo Python con hashes.

Se publica un commit de corrección en la misma rama después de validar. El SHA,
el run y los cinco resultados del HEAD se registran en la descripción del
[PR #16](https://github.com/danipello09/inventory-sales-saas/pull/16) tras ejecutarse;
no se atribuye un run anterior a un commit nuevo. El PR sigue en borrador para
revisión humana. No se hace merge, no se cierran issues ni se declara producción.
