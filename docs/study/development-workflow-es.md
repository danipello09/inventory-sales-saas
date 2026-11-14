# Guía de estudio: desarrollo y colaboración

> Nota de versi?n: las explicaciones de ?todav?a no implementado? de esta gu?a
> corresponden al bootstrap de Fase 2. PR #13/#14/#15 ya est?n integrados y PR #16
> a?ade identidad/organizaciones. Para el estado actual y el arranque seguro con
> volumen nuevo consulta [backend](../development/identity-backend.md) y
> [cutover](../development/identity-cutover.md). Cat?logo, inventario y ventas
> contin?an pendientes; esta gu?a no autoriza usar el volumen anterior.


Este proyecto está en **Fase 2: arquitectura e infraestructura**. Ya ejecuta Django,
React, PostgreSQL y Mailpit con Docker Compose, con cinco jobs de CI. Todavía no
implementa usuarios de negocio, organizaciones, catálogo, inventario, ventas ni
aislamiento multiempresa. Un documento de diseño no equivale a funcionalidad.

## 1. Monorepo y arquitectura

Un monorepo guarda componentes relacionados en un repositorio Git. Aquí `backend/`,
`frontend/`, `docs/`, `.github/` y `compose.yaml` comparten historial y PR. Permite
revisar juntos una futura API, su consumidor y su documentación. No implica que
todos los procesos se ejecuten juntos o se desplieguen siempre de la misma manera.

ADR-003 está en el [registro de decisiones](../adr/README.md). El backend se diseña
como monolito modular: una aplicación con módulos internos, sin introducir
microservicios antes de necesitarlos. Esos módulos de negocio aún no existen.
El [README](../../README.md#architecture) muestra la topología local actual.

## 2. Django y React

Django ejecuta el servidor Python: rutas, ORM, migraciones y middleware. Django
REST Framework aporta herramientas para futuras APIs. Hoy `backend/config/urls.py`
solo registra `/health/`, que devuelve `{"status":"ok"}`. Las aplicaciones de auth
de Django están instaladas, pero no hay flujos de registro/login ni rutas de
administración o negocio registradas.

React construye interfaces mediante componentes. TypeScript comprueba tipos antes
de ejecutar; no valida automáticamente los datos recibidos por HTTP. Vite sirve
el frontend en desarrollo y genera el build junto con TypeScript.
`frontend/src/App.tsx` muestra la pantalla inicial de Fase 2, no un dashboard.
El proxy `/api/` de Vite está configurado, pero `/api/v1/` todavía devuelve 404.

## 3. API REST

Una API define cómo se comunican programas. REST organiza la interacción alrededor
de recursos y de la semántica HTTP: un futuro `GET /api/v1/products/` consultaría
productos y un `POST` podría crearlos si el usuario tiene permiso. Usar JSON por sí
solo no demuestra que una API cumpla todas las restricciones de REST.

El [contrato API](../architecture/api-contract.md) es un diseño pendiente de detalle,
no una lista de endpoints disponibles. Sesiones y CSRF son la estrategia aprobada;
no estamos implementando JWT ni autenticación comercial en esta fase.

## 4. PostgreSQL frente a SQLite

PostgreSQL es un servidor de base de datos con conexiones concurrentes, transacciones
y controles de integridad; es el motor aprobado para el entorno integrado. SQLite
guarda una base local en un archivo y facilita smoke checks independientes. Sus
resultados no sustituyen verificar migraciones y SQL en PostgreSQL.

En `backend/config/settings.py`, `DATABASE_HOST` selecciona PostgreSQL; si está
vacío o ausente se usa SQLite. Dentro de Compose el host es `db`. En CI Django
corre en el runner y accede al servicio en `127.0.0.1:5432`. `localhost` se refiere
siempre al entorno donde corre el proceso que intenta conectarse.

`backend/tests/test_database.py` ejecuta SQL y verifica una migración. CI exige el
proveedor con `EXPECT_DATABASE_VENDOR`: configurar el nombre del motor no demuestra
una conexión. pytest-django crea una base separada; nunca debe usar producción.

## 5. Docker, Dockerfile y Docker Compose

| Concepto | Función en el repositorio |
| --- | --- |
| Imagen | Empaqueta filesystem, runtime y dependencias para ejecutar procesos |
| Contenedor | Instancia de ejecución de una imagen; comparte el kernel del entorno Linux de Docker |
| Dockerfile | Receta para construir una imagen; instala dependencias y configura el usuario de ejecución |
| Compose | Declara servicios, redes, volúmenes y healthchecks; aquí db, mailpit, backend y frontend |

El bind mount del código permite editar sin reconstruir por cada cambio. El volumen
anónimo en `/app/node_modules` separa dependencias Linux de las de Windows. El
volumen nombrado PostgreSQL conserva datos aunque se recree el contenedor.
No se borra para resolver rutinariamente una contraseña o un reinicio.

Una etiqueta de imagen fija una versión legible; un digest fija contenido. Este
proyecto usa tags de versión, no digests. Docker ayuda a repetir el entorno, pero
no elimina diferencias de plataforma ni sustituye revisar actualizaciones.

## 6. Mailpit

Mailpit captura SMTP y permite inspeccionar correos en una bandeja web local, sin
entregarlos a personas. Django en Compose apunta a `mailpit:1025`; el navegador abre
`http://127.0.0.1:8025/`. No tiene relay externo configurado.

Fuera de Compose Django usa correo de consola por defecto. La captura SMTP existe;
el servicio de invitaciones sigue planeado. Usa destinatarios ficticios `.test`,
nunca direcciones, datos personales o tokens reales.

## 7. Git y GitHub

Git mantiene versiones de forma distribuida. GitHub aloja el repositorio y añade
issues, PR, revisiones y Actions. Puedes hacer commits sin Internet; para publicar
necesitas comunicarte con el remoto.

El working tree contiene archivos editables; el índice o staging contiene lo que
irá al próximo commit. `git diff` muestra cambios sin preparar, `git diff --cached`
muestra lo preparado y `git status` también muestra archivos nuevos. `.gitignore`
no elimina archivos ya versionados ni secretos que ya están en el historial.

## 8. Branch, commit, push, pull request y merge

| Concepto | Significado |
| --- | --- |
| Branch | Referencia a una línea de trabajo, como docs/issue-7-onboarding |
| Commit | Instantánea versionada de los cambios preparados, con autor y mensaje |
| Push | Publicar commits en el remoto; no integra automáticamente a main |
| Pull request | Propuesta de integración con diff, conversación y checks |
| Merge | Integrar el trabajo aceptado en la rama destino |

La secuencia es issue → rama desde main actualizado → cambios → validación →
commit → push → PR borrador → CI y revisión → aceptación → merge autorizado.
Entregar un borrador no significa que el trabajo ya esté integrado. Consulta la
[guía de contribución](../../CONTRIBUTING.md) para comandos y criterios reales.

## 9. CI y CD

La **integración continua (CI)** comprueba automáticamente cambios al integrarlos
frecuentemente. La **entrega continua** mantiene cambios verificados listos para
publicar; el **despliegue continuo** automatiza además su paso a un entorno,
normalmente producción. Este repositorio implementa CI, no un pipeline de CD.

Un workflow responde a eventos y contiene jobs. Aquí corren independientemente
en runners Ubuntu. Cada job contiene pasos que comparten su entorno. Una caché
reutiliza descargas; no demuestra que se hayan ejecutado los tests.
Un job verde solo prueba los comandos que corrieron sobre ese commit.

## 10. Los cinco jobs reales

| Job ID | Qué valida |
| --- | --- |
| backend-quality | Python 3.12, Django check, Ruff y pytest con SQLite |
| frontend-quality | Node 22, npm ci, ESLint, Vitest y build TypeScript/Vite |
| postgres-integration | PostgreSQL 17, readiness, migraciones, conexión/proveedor, drift y pytest con base separada |
| compose-validation | Modelo Compose y cuatro servicios esperados; no construye imágenes ni levanta el stack |
| dependency-audit | Auditorías npm de producción y árbol completo con umbrales explícitos; no audita Python |

El [workflow](../../.github/workflows/bootstrap-validation.yml) corre en PR a main,
push a main y dispatch manual. Los borradores también ejecutan CI. Revisa el último
commit: cancelado, omitido o en cola no significa aprobado. La [guía CI](../development/ci.md)
explica cómo abrir los logs del primer paso fallido.

## 11. pytest, Ruff, Vitest y ESLint

pytest ejecuta pruebas Python; pytest-django integra settings, migraciones y base
de prueba. Ruff inspecciona Python, incluidos imports y errores de estilo. Vitest
ejecuta pruebas JS/TS; ESLint analiza JS/TS y reglas de React. El build ejecuta
`tsc -b` y Vite: aprobar lint no garantiza compilar.

El backend prueba health y conexión/migraciones. El frontend solo comprueba que
App exporte una función; no demuestra interacción de usuario. No se afirma una
cifra de cobertura ni seguridad multiempresa con estos smoke tests.

## 12. Healthchecks

Un healthcheck ejecuta una comprobación periódica: PostgreSQL usa `pg_isready`,
backend consulta `/health/`, frontend comprueba HTTP y Mailpit usa `readyz`.
`depends_on: condition: service_healthy` espera que la dependencia esté saludable
antes de iniciar el servicio dependiente.

Proceso iniciado, servicio saludable y aplicación lista para negocio son cosas
distintas. `/health/` no consulta la base y puede responder 200 antes de migrar.
Los healthchecks por sí solos no reinician contenedores unhealthy. `unless-stopped`
actúa cuando termina un proceso; las migraciones siguen siendo explícitas.

## 13. Lockfiles y dependencias

`frontend/package.json` declara dependencias y scripts; `package-lock.json` registra
resoluciones transitivas e integridad. `npm ci` instala ese árbol y falla si ambos
archivos discrepan. No se versiona node_modules.

`backend/requirements.txt` fija versiones directas, pero no equivale a un lock
transitivo completo con hashes. La caché acelera descargas, no sustituye instalación,
lockfiles ni auditoría.

Una dependencia transitiva llega mediante otra. Un aviso puede propagarse a varios
paquetes: nueve entradas no equivalen necesariamente a nueve fallos independientes.
Las herramientas de desarrollo también ejecutan código en tu máquina o CI.
La política bloquea cualquier vulnerabilidad de producción y altas/críticas del
árbol completo; las moderadas de desarrollo siguen visibles. Pasar el umbral no
significa cero vulnerabilidades. Consulta [seguridad](../../SECURITY.md).

## 14. Migraciones de Django

Una migración versiona cambios del esquema. `makemigrations` genera archivos a
partir de cambios en modelos; `migrate` aplica los pendientes.
`makemigrations --check --dry-run` falla si hacen falta archivos nuevos. Se revisan
y versionan las migraciones; no se borran las ya aplicadas para ocultar conflictos.

Las 18 migraciones estándar del informe #6 pertenecen a Django, no a catálogo o
ventas. Desde la raíz con Compose activo, en PowerShell o Bash:

```text
docker compose exec backend python manage.py migrate --noinput
```

## 15. Aislamiento multiempresa: aprobado frente a implementado

Multi-tenancy significa atender organizaciones con separación de datos y permisos.
ADR-001 propone una base PostgreSQL compartida con aislamiento lógico. ADR-004 exige
autorización centralizada, integridad relacional y pruebas de aislamiento; RLS se
contempla como defensa adicional, no como garantía ya implementada.

No basta un campo organization_id o aceptar el ID del cliente. La organización debe
derivarse de la membresía autenticada; consultas y operaciones deben limitarse a
ella, con restricciones y pruebas negativas. **Está diseñado, pero no implementado
ni certificado por los tests actuales.**

También están pendientes el usuario de email único, membresías, invitaciones,
transacciones de inventario/ventas, importes decimales y UUID de entidades de negocio.
Se estudian en los ADR/TD y el [modelo conceptual](../architecture/data-model.md).

## 16. Cómo explicar el proyecto en una entrevista

Una presentación de aproximadamente un minuto:

> Estoy construyendo un SaaS de inventario y ventas en un monorepo con React y
> TypeScript, Django REST Framework y PostgreSQL. Está en Fase 2: puedo reproducir
> el entorno con Docker Compose, capturar correo con Mailpit y ejecutar cinco jobs
> de CI, incluidos migraciones y tests con PostgreSQL real. Los ADR definen una base
> compartida con aislamiento por organización y sesiones protegidas por CSRF.
> Los módulos de negocio y ese aislamiento todavía no están implementados.
> Mi trabajo actual demuestra infraestructura verificable, decisiones explícitas
> y revisión mediante pull requests.

Después explica un límite concreto, como Compose sin arranque completo en CI o el
alcance smoke de los tests. Describir evidencia y límites es más preciso que afirmar
que ya existe un producto listo para clientes.

## 17. Preguntas de entrevista

| Pregunta | Respuesta breve |
| --- | --- |
| ¿Por qué monorepo? | Mantiene contratos, código y documentación relacionados en un PR; exige controlar el alcance. |
| ¿Por qué PostgreSQL si SQLite pasa? | Son motores distintos y necesito probar en el motor integrado elegido. |
| ¿Por qué no microservicios? | Un monolito modular reduce complejidad operativa en esta fase; aún no hay una necesidad medida de separación. |
| ¿Por qué migrate después de up? | El servidor y su healthcheck pueden arrancar con el esquema pendiente. |
| ¿Imagen frente a volumen? | La imagen empaqueta ejecución; el volumen guarda datos fuera del ciclo del contenedor. |
| ¿Por qué npm ci? | Instala desde lockfile y rechaza inconsistencias con el manifest. |
| ¿Caché verde equivale a tests verdes? | No; debe ejecutarse el comando de pruebas y revisarse su resultado. |
| ¿Por qué sesiones y CSRF? | Es el diseño same-origin aprobado; HttpOnly limita lectura desde JS y CSRF protege solicitudes autenticadas inseguras. El login aún no existe. |
| ¿Cómo separas ventas entre empresas? | Falta implementarlo: membresía autenticada, scoping, integridad relacional y pruebas de denegación según ADR-004. |
| ¿Qué no prueba CI? | Negocio, tenant isolation, SMTP/HMR, arranque completo de imágenes y seguridad de producción. |
| ¿Por qué no forzar audit fix? | Puede romper contratos; reviso severidad y actualizaciones compatibles sin ocultar deuda. |
| ¿Qué significa listo para merge? | Criterios completos, cinco checks actuales, conflictos resueltos y aceptación humana; push no equivale a aprobación. |

## Orden de estudio recomendado

1. Ejecuta el [quick start](../../README.md#quick-start-with-docker-compose) y explica
   cada servicio, URL y volumen sin memorizar comandos aislados.
2. Recorre health, App y settings para distinguir código real de contratos futuros.
3. Practica Git y revisa un PR con los cinco jobs y sus logs.
4. Lee ADR-001/002/004 y explica qué garantías faltan implementar y probar.
5. Repasa lockfiles, migraciones y seguridad local; ensaya la presentación anterior.

Esta guía no sustituye las instrucciones operativas en inglés ni autoriza empezar
el Issue #8 o implementar funcionalidades fuera de la tarea asignada.
