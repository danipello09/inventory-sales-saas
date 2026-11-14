# Issue #8 — revisión reproducible de Fase 2

Fecha: 13 de noviembre de 2026 (America/Bogota). Base main:
`757cc5d2a0f8eee0292ecb737fd72cadea343e71`.
Rama: `chore/issue-8-phase-2-review`. No se declara cierre formal de Fase 2.

## Estado y alcance

Issues #4–#6 integrados. Issue #7 y [PR #13](https://github.com/danipello09/inventory-sales-saas/pull/13)
siguen abiertos; el PR permanece en borrador y sus cinco checks sobre `6821737`
están aprobados. No se fusionó, modificó ni duplicó ese trabajo. La revisión
ejecutada corresponde al código y documentación de main, sin las guías pendientes
del PR #13. La aceptación editorial final de esas guías sigue dependiendo de él.

El comando ejecutado desde esta rama fue `python scripts/verify_phase2.py`.
El script clona origin en una carpeta nueva del directorio temporal, fija el SHA
anterior y usa un proyecto Compose único `mission-phase2-*`, puertos libres en
loopback, base/usuario propios y valores aleatorios desechables. No lee `.env`
del checkout de desarrollo. No modifica datos o contenedores preexistentes.

Entorno observado: Windows, Python 3.12.10, Docker Engine 29.8.1 y Compose 5.5.1;
imágenes Python 3.12.16, Node 22.23.5, PostgreSQL 17.12 y Mailpit 1.33.1.
El build usó cachés normales de Docker; no se afirma un build sin caché, offline,
una máquina vacía ni prueba visual interactiva del navegador.

## Matriz de evidencia real

La [evidencia estructurada](evidence/issue-8-results.json) conserva 32 comprobaciones
del run, sin secretos ni rutas personales. Los logs detallados permanecen locales
en el directorio temporal `inventory-phase2-*` indicado por el script; se redactan
automáticamente los valores efímeros antes de escribirlos.

| Comprobación | Resultado observado |
| --- | --- |
| `git clone`, checkout SHA y status | Código 0; fuente remota en clon limpio separado. |
| `docker compose ... config --quiet` | 0; interpolación y modelo válidos. |
| `docker compose ... build` | 0; ambas imágenes construidas con instalación declarada en Dockerfiles, incluida npm ci (puede reutilizar capas). |
| `up -d --wait --wait-timeout 120` | 0; cuatro servicios saludables en 21.75 s. |
| `python manage.py migrate --noinput` | 0; 18 migraciones Django sobre base nueva. |
| Conexión y consulta SQL de Django | Proveedor postgresql, base phase2_review, PostgreSQL 17.12 real. |
| `python manage.py check` | 0. |
| `python -m ruff check .` | 0. |
| `python -m pytest -q` | 0; 2 pruebas contra PostgreSQL. |
| `makemigrations --check --dry-run` | 0; No changes detected. |
| `npm run lint` | 0. |
| `npm test` | 0; 1 prueba. |
| `npm run build` | 0; TypeScript y Vite. |
| `npm audit --omit=dev --audit-level=low` | 0; cero vulnerabilidades conocidas de producción. |
| `npm audit --audit-level=high` | 0 por umbral; 9 alertas moderadas de desarrollo visibles. |
| GET Django `/health/` | 200 y status ok. |
| GET Vite `/` y `/src/App.tsx` | 200; HTML y módulo transformado real. |
| GET Vite `/api/v1/` | 404 generado por Django, comprobando proxy; no se inventa un endpoint comercial. |
| GET Mailpit web | 200. |
| `send_mail` a recipient@inventory.test | 1 entrega; API Mailpit confirma asunto único de la misión, sin relay externo. |
| Persistencia | Tabla/marcador propios creados, contenedor db recreado con ID distinto, mismo marcador y 18 migraciones conservados; tabla propia eliminada. |
| Seguridad topológica | Cuatro servicios esperados; DB sin puerto de host; publicaciones backend/frontend/Mailpit solo en 127.0.0.1. |
| Limpieza en finally | 0; down --volumes ejecutado únicamente con el proyecto único y clon recién creados. |

Tras finalizar, los cuatro contenedores originales `inventory-sales-saas-*`
continuaban activos y healthy. No se borró su volumen ni se aplicaron migraciones
en él. Las comprobaciones del script fallan con código no cero; no usa
continue-on-error ni convierte una auditoría fallida en éxito.

## Supuestos de seguridad y riesgos residuales

- Infraestructura funcional no equivale a seguridad de producción. DEBUG y
  servidores de desarrollo se usan solo en la red local aislada de esta prueba.
- DB usa el usuario inicializador de la imagen; no es una política de privilegios
  de producción. Los procesos app no son root. SMTP no tiene relay configurado.
- Puerto localhost limita exposición, pero procesos locales con acceso pueden
  ver servicios/datos. Backend/frontend/Mailpit tienen salida por host_access.
- La deuda minimatch permanece visible; umbrales: cualquier finding de producción
  bloquea, alta/crítica del árbol completo bloquea. No hay auditoría Python en CI
  ni lock transitivo Python completo. No se actualizan dependencias en este issue.
- Tests actuales son smoke, sin negocio ni tenant isolation. Health HTTP no prueba
  migraciones ni DB; por eso se comprobaron mediante pasos separados.
- Tags de imágenes son versiones exactas, no digests. Cachés, registro y red son
  dependencias externas. Una carrera de puerto libre es posible: el error no se oculta.
- CI no ejecuta este stack completo por defecto; su job Compose es estático y el
  PostgreSQL usa service container. Este run local aporta evidencia distinta.

## Documentación frente a comportamiento

Las instrucciones operativas de Docker/main coinciden con servicios, puertos,
migraciones explícitas, SMTP y persistencia. La frase de setup que decía que el
entorno integrado usaría PostgreSQL en el futuro ya está corregida en PR #13;
se conserva esa dependencia en lugar de introducir un diff duplicado. Los ADR
son decisiones aprobadas, no pruebas de aislamiento implementado. No se encontró
un fallo bloqueante del stack de main. La auditoría de PR #13 ya distingue el
estado histórico de los informes anteriores.

Antes de publicar se ejecutaron Ruff sobre el script, `git diff --check`, revisión
de rutas/diff y escaneo de valores secretos y marcadores. Los checks remotos del
HEAD y enlace del PR se mantienen en su descripción; no se confunden con este run
de Docker local. La revisión asistida por IA requiere aceptación humana posterior.

## Reproducción y límites de limpieza

Con Python 3.12 y Docker Linux disponibles: `python scripts/verify_phase2.py`.
`--ref <SHA>` permite revisar otra revisión explícita; por defecto fija la base
validada aquí. El script necesita acceso a GitHub y registros. Solo limpia su
proyecto aleatorio tras comprobar que no existían contenedores/volúmenes con esa
etiqueta antes de empezar. Retiene clon, resultados y log local para inspección.
No ejecute comandos de limpieza sobre el proyecto de desarrollo para reproducirlo.

Queda pendiente la revisión humana de Fase 2 y la documentación del PR #13. Este
PR no cierra issues, no fusiona cambios y no autoriza despliegue de producción.
