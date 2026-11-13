# Issue #7: validación de onboarding y contribuciones

Fecha: 13 de noviembre de 2026 (America/Bogota).
Rama: `docs/issue-7-onboarding`, inicialmente limpia e idéntica a `origin/main`
después de `git fetch origin`, en `757cc5d2a0f8eee0292ecb737fd72cadea343e71`.
Los Issues #4, #5 y #6 se consultaron en GitHub y estaban cerrados; #7 estaba abierto.

## Auditoría documental

Se revisaron todos los Markdown versionados, template PR, workflow, Compose,
Dockerfiles, variables de ejemplo, dependencias/scripts y código smoke existente.
El README principal tenía dos líneas y presentaba el objetivo multiempresa sin
aclarar que no estaba implementado. Faltaban CONTRIBUTING, SECURITY y apuntes de
estudio. La guía local no separaba explícitamente activación Bash/PowerShell y
decía que el entorno integrado usaría PostgreSQL en el futuro, aunque ya lo usa.
El estado global del índice ADR decía implementación pendiente, incluso para la
infraestructura ya entregada. CI remitía a una deuda en el Issue #6 ya cerrado.

Las guías técnicas existentes eran útiles; no se eliminaron ni se reescribieron
los informes históricos para hacerlos parecer evidencia actual. No se cambió
ninguna decisión ADR/TD, contrato comercial, código, dependencia o configuración.

## Archivos y mejoras

- `README.md`: propósito, estado honesto, stack, arquitectura Mermaid, estructura,
  prerrequisitos, quick start Docker por shell, URLs, migraciones, checks, CI y roadmap.
- `CONTRIBUTING.md`: issues, ramas, commits, staging explícito, forks, conflictos,
  PR borrador compatible con template, evidencia, revisión y criterios de merge.
- `SECURITY.md`: variables, secretos, exposición, datos sintéticos, deuda npm,
  política existente y reporte privado condicional sin inventar contactos/SLA.
- `docs/study/development-workflow-es.md`: 17 temas con ejemplos reales,
  distinción implementado/planeado, respuestas de entrevista y orden de estudio.
- `docs/development/README.md`: onboarding e índice de evidencia; comandos host
  diferenciados por shell y corrección del estado PostgreSQL.
- `docs/development/docker-compose.md`: enlaces de onboarding/seguridad y límite
  entre infraestructura SMTP y lógica futura de invitaciones.
- `docs/development/ci.md`: evidencia npm fechada y seguimiento tras cierre de #6.
- `docs/adr/README.md`: solo progreso de implementación y navegación; decisiones intactas.
- Este informe: auditoría, alcance y resultados verificables.

## Validación ejecutada

Se ejecutaron las siguientes comprobaciones en Windows con Python 3.12.10,
Docker Engine 29.8.1 y Docker Compose 5.5.1. Los scripts de inspección se ejecutaron
por stdin, sin agregar herramientas/dependencias ni archivos generados al repo.

| Comprobación/comando | Resultado real |
| --- | --- |
| `git fetch origin`, rama/estado y HEAD frente a origin/main | 0; rama correcta, árbol limpio al inicio, base confirmada. |
| Checker Python de todos los Markdown versionados/nuevos no ignorados | 0; 15 archivos, 70 enlaces internos y 8 fragmentos/anchors válidos. Resuelve destinos respecto al documento y comprueba headings, excluyendo bloques de código y URLs externas. |
| `bash -n` en contenedor Node 22 sobre bloques Bash | 0; 2 bloques analizados, no ejecutados. |
| Parser PowerShell `Language.Parser.ParseInput` | Sin errores; 13 bloques analizados, no ejecutados. |
| `docker compose --env-file .env.example config --quiet` con variables ficticias explícitas | 0; no se imprimió configuración resuelta ni se leyó el .env local. |
| Inspección Compose JSON en memoria | 0; cuatro servicios, puertos 8000/5173/8025/1025 ligados a 127.0.0.1, DB sin puerto publicado, db/mailpit como hosts internos, dependencias saludables, healthchecks y volumen persistente correctos. |
| Comparación de scripts npm y jobs/rutas contra código/configuración | 0; lint/test/build y los cinco jobs coinciden; existen manage.py, requirements, tests, App y template PR. |
| GET badge del workflow real con branch=main | HTTP 200, image/svg+xml. |
| GET localhost Django `/health/`, React `/` y Mailpit `/` en sus puertos predeterminados | HTTP 200 en las tres URLs, usando servicios locales ya activos. |
| `git check-ignore .env` | 0; .env ignorado. |
| `git diff --check` | 0. |

El primer intento de análisis Bash falló por la conversión automática de stdin a
CRLF de Windows en el script comprobador. Se repitió con bytes UTF-8, sin alterar
el contenido de los documentos, y el parser aprobó los dos bloques.

No se ejecutaron de nuevo pytest, Ruff, Vitest, ESLint o build **localmente** en este
issue documental. No se declara un arranque limpio, reconstrucción de imágenes,
render de Mermaid o prueba completa de los ejemplos interactivos. Los scripts de
shell se analizaron sintácticamente; solo los comandos indicados se ejecutaron.
El bootstrap completo y sign-off pertenecen al Issue #8, que no se inició.
La evidencia histórica #4–#6 permanece identificada por fecha.

## Publicación y pendientes

Commit inicial `07b4d16c39d957f53c1ac49a1759f8b7e13f23db`, publicado en
`origin/docs/issue-7-onboarding`. Se creó el
[PR #13](https://github.com/danipello09/inventory-sales-saas/pull/13), borrador contra
main, vinculado al Issue #7 y compatible con las secciones del template existente.

Se consultaron jobs/pasos y logs reales de
[Quality checks #11](https://github.com/danipello09/inventory-sales-saas/actions/runs/43525073994),
que terminó en **success**. Ningún paso falló ni fue omitido:

| Job | Resultado remoto real |
| --- | --- |
| Django checks | success; Python 3.12.16, check/Ruff y 2 pruebas SQLite. |
| React checks | success; Node 22.23.4/npm 10.9.9, npm ci/lint, 1 prueba y build de 29 módulos. |
| PostgreSQL integration | success; migraciones, conexión postgresql a inventory_ci en PostgreSQL 17.12, sin drift y 2 pruebas. |
| Docker Compose validation | success; modelo válido y cuatro servicios esperados. |
| npm dependency audit | success por umbrales; 0 producción y 9 moderadas de desarrollo visibles. No se afirma remediación. |

Se revisaron los nueve Markdown completos, el diff preparado y las rutas. El
escaneo de marcadores de conflicto, patrones de tokens y valores secretos del
`.env` local no encontró coincidencias en los cambios preparados. El índice no
contiene código, configuración, dependencias, lockfiles o artefactos generados.
`git diff --cached --check` pasó antes del commit.

Un commit posterior añade esta evidencia; los checks de su HEAD se registran en
la descripción del PR para no atribuirle una ejecución anterior. La revisión fue
asistida por IA; falta revisión humana del contenido, alcance y cinco checks
actuales antes del merge. No se promete soporte de seguridad ni canal privado
habilitado; la guía explica qué hacer si esa función no está disponible.

No se hizo merge, no se cerró manualmente #7, no se alteró protección de ramas
y no se empezó #8. No se conocen bloqueos técnicos tras estas validaciones.
