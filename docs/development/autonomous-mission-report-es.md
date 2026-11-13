# Informe de misión autónoma — Fase 2 y primer backend

Fecha: 13 de noviembre de 2026 (America/Bogota).

## Resumen ejecutivo y estado inicial

Se verificó la infraestructura de main desde un clon remoto limpio y se entregó
la revisión del Issue #8 en PR borrador separado. Después se especificó identidad/
organizaciones en otro PR y se implementó una primera vertical backend con usuario
personalizado, organizaciones, membresías, sesiones y CSRF. Las pruebas locales
finales pasan con SQLite y PostgreSQL real, incluido un recorrido HTTP con cookies.

Al iniciar, main era `757cc5d2a0f8eee0292ecb737fd72cadea343e71`, con #4/#5/#6
integrados. El checkout original estaba limpio en docs/issue-7-onboarding. Issue #7
y PR #13 seguían abiertos; PR #13 en borrador, mergeable y con cinco checks del
HEAD 6821737 aprobados. Issue #8 estaba abierto. Se consultaron GitHub, Git,
Compose, código, workflow y ADR/TD; no se asumió integración de #7.

## Seguimiento

| Etapa | Estado | Evidencia | PR |
| --- | --- | --- | --- |
| A: Inspección | Completada | refs/estado consultados; PR #13 conservado; ADR/TD revisados | [#13 existente](https://github.com/danipello09/inventory-sales-saas/pull/13) |
| B: Issue #8 | Entregada para revisión; Fase 2 no cerrada | 32 comprobaciones de clon/Compose/DB/SMTP/persistencia; cinco jobs remotos success | [#14](https://github.com/danipello09/inventory-sales-saas/pull/14) |
| C: Diseño Fase 3 | Entregado para revisión | Contrato detallado, JSON/enlaces comprobados, cinco jobs success | [#15](https://github.com/danipello09/inventory-sales-saas/pull/15) |
| D: Backend inicial | Implementado, publicado y verificado en CI | 52 tests SQLite, 52 PostgreSQL; 27 registros DB/HTTP/guard | [#16](https://github.com/danipello09/inventory-sales-saas/pull/16) |
| E: Calidad | Gates locales y cinco jobs de los tres PR aprobados | Ruff, check, drift, diff/rutas/secretos; runs #13/#14/#15 | PR #14/#15/#16 separados, sin diffs duplicados |

## Ramas, commits y archivos

Se crearon worktrees separados para no cambiar innecesariamente el checkout #7:

- `chore/issue-8-phase-2-review`, desde main; commit `0086736`:
  `chore: verify phase 2 from an isolated clean clone`. Incluye
  scripts/verify_phase2.py, informe Issue #8 y JSON sanitizado de evidencia.
- `docs/phase-3-identity-design`, desde el mismo main; commit `3ba5489`:
  `docs: specify identity and organization backend contract`. Solo añade
  docs/architecture/identity-organizations.md.
- `feat/phase-3-identity-organizations`, desde el mismo main; commit funcional
  `77dc8b2`: `feat: add session identity and scoped organization backend`. El commit
  posterior solo registra evidencia y se identifica por SHA en su PR. Incluye apps accounts,
  organizations e identity; migraciones, tests, configuración de usuario/cookies,
  rutas API, verificador PostgreSQL y documentación propia.

Las ramas de diseño e implementación apuntan a main de forma independiente. La
implementación declara dependencia de revisión de #15 sin copiar sus commits,
conservando los cinco checks que filtran PR hacia main. No se mezcló Issue #8,
diseño y backend en un PR ni se reescribió historial remoto.

## Funcionalidad real

- Usuario UUID con email único/canónico, contraseña con hashing y validación Django.
- Organization y Membership UUID; un máximo de una membresía por usuario, roles
  ADMIN/STAFF y estado activo/inactivo de membresía; organización ACTIVE/SUSPENDED.
- Registro transaccional de usuario/organización/ADMIN y establecimiento de sesión.
- Login, logout, me y bootstrap de CSRF; cookies HttpOnly/SameSite y Secure por defecto.
- Consulta de organización propia y actualización de nombre solo por ADMIN activo.
- Scoping derivado del usuario, rechazo de campos extra/IDs/privilegios y bloqueo
  de tenant operations para suspensión, membresía inactiva o cuenta plataforma.
- Restricciones reales e integridad FK, migraciones nuevas y guard de esquema antiguo.

No se implementaron catálogo, inventario, ventas, reportes, invitaciones ni UI
comercial. El frontend conserva su pantalla inicial. La garantía de aislamiento
probada corresponde a metadata de organización; no certifica módulos inexistentes.

## Pruebas y evidencia real

Issue #8 se ejecutó con `python scripts/verify_phase2.py` sobre clon remoto fijado
en main. Build con cachés normales, cuatro servicios healthy, migraciones y
conexión PostgreSQL 17.12, HTTP/frontend/proxy, correo `.test` capturado por Mailpit,
Ruff/pytest, ESLint/Vitest/build y auditorías pasaron. La persistencia se verificó
con marcador propio y recreación del contenedor DB; la limpieza solo afectó al
proyecto aleatorio creado por la misión. No se afirma build sin caché ni QA visual.

En backend se creó un venv Python 3.12.10 y se instalaron requirements sin cambios.
`manage.py check`, Ruff y `makemigrations --check --dry-run` pasaron. La suite final
tuvo **52 passed en SQLite (18.96 s)** y **52 passed en PostgreSQL (20.51 s)**.
Las pruebas incluyen registro/errores/rollback, unicidad por email y case variants,
sesiones/rotación/logout, CSRF anónimo y autenticado, Origin hostil, cookie flags,
roles y dos organizaciones, suspensión/inactividad, campos inyectados y DB/FKs.

`scripts/verify_identity_database.py` creó dos bases propias en PostgreSQL nuevo:
una migrada con el main antiguo real (18 migraciones) y otra con custom user
(20 migraciones). La nueva orden migrate rechazó la base antigua con exit 1
esperado y preservó tablas/historial/marcador. La base nueva migró dos veces sin
drift, usa UUID y no crea auth_user. El verificador terminó en exit 0.

Un servidor HTTP real confirmó 403 sin CSRF, token 200, registro 201, me/org 200,
rename 200, logout 204, acceso posterior 401 y login 200 con cookies. El proceso
y su PostgreSQL/volumen temporal se limpiaron. Los cuatro servicios originales
seguían healthy. No se ejecutaron migraciones ni escrituras sobre su base.

Fallos encontrados se reprodujeron y corrigieron: código de error DRF distinto al
contrato; fixture de moneda demasiado larga para comprobar el enum en PostgreSQL;
y gate JSON explícito tras interacción de multipart con middleware CSRF. No se
borraron assertions ni se ocultaron errores. Véase [evidencia backend](identity-validation.md).

CI de #14: [run #13](https://github.com/danipello09/inventory-sales-saas/actions/runs/43526691315),
cinco jobs success. CI de #15:
[run #14](https://github.com/danipello09/inventory-sales-saas/actions/runs/43527149814),
cinco jobs success. Backend:
[run #15](https://github.com/danipello09/inventory-sales-saas/actions/runs/43529168981),
cinco jobs success sobre 77dc8b2: Django con 52 tests (9.40 s), PostgreSQL 17.12 con
52 tests (8.29 s), React con lint/1 test/build, Compose válido y auditoría con
0 producción/9 moderadas de desarrollo. Se inspeccionaron pasos y logs reales.
El último commit documental añade esta evidencia; sus checks se registran además
en la descripción del PR tras ejecutarse, sin atribuirle un run anterior.
Frontend se ejecutó localmente en la revisión de Fase 2 y remotamente en los tres
PR; no se repitió localmente en el slice backend.

## Riesgos, bloqueos y trabajo pendiente

La conversión del volumen antiguo al modelo personalizado **no se realizó** y
requiere autorización para un plan independiente que preserve usuarios y referencias.
El desarrollo nuevo debe usar otra base/proyecto. No se propone borrar datos ni
usar fake migrations como solución. Esta restricción no bloquea probar/entregar
la implementación sobre bases nuevas.

Permanecen las nueve alertas moderadas npm de desarrollo conocidas, cero de
producción en la auditoría de Fase 2; no se remediaron ni ocultaron. Se conservan
umbrales y cinco jobs. No hay auditoría Python automática ni lock transitivo
Python completo. No hay rate limiting, verificación/recuperación de email,
operación de producción, ni conversión legacy. La respuesta de registro duplicado
puede revelar existencia de cuenta. La API de desarrollo no debe exponerse públicamente.

Faltan aceptación humana de #13/#14/#15 y del backend, cierre formal de Fase 2 por
su responsable y todo el negocio de inventario/ventas. No se modificaron ADR/TD,
protecciones de ramas ni servicios de pago. No se fusionaron PR ni cerraron issues.
No se dispone de métrica del saldo de la cuenta Codex y no se inventa consumo.

## Siguiente acción exacta y conceptos para estudiar

Al regresar: revisar primero #13 (onboarding), después la evidencia #14 sin marcar
automáticamente Fase 2 cerrada, luego el contrato #15 y finalmente el PR backend
con sus cinco checks sobre el último commit. Para reproducir la vertical, entrar
en su worktree y ejecutar el verificador con el Python del venv como indica
[identity-backend.md](identity-backend.md). No usar la base/volumen originales.
Una futura conversión de datos debe aprobarse expresamente antes de ejecutarse.

Conceptos clave: una sesión guarda identidad en el servidor y usa cookie; CSRF
protege mutaciones autenticadas y también login anónimo; HttpOnly limita lectura
desde JS, pero no sustituye CSRF. Unicidad y FKs en DB protegen escrituras que no
pasan por serializers. La transacción evita registro parcial y los locks permiten
recomprobar permisos al actualizar. Un custom user debe existir en su migración
inicial y afecta dependencias de admin; cambiar settings no convierte datos antiguos.
CI prueba un commit concreto; salud HTTP, DB conectada y reglas de negocio son
garantías distintas. Un PR borrador entrega evidencia para revisión, no autorización
para integrar o desplegar.

La estimación del MVP es cualitativa: infraestructura reproducible y una vertical
fundacional de identidad/organizaciones implementadas; los flujos centrales de
catálogo, stock y ventas siguen ausentes. Sin backlog ponderado ni criterios de
aceptación completos no hay base para un porcentaje defendible. No se presenta
este avance de infraestructura como un MVP comercial terminado.
