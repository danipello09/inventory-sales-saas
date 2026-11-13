# Issue #4: corrección y validación local

Fecha: 13 de noviembre de 2026 (America/Bogota).
Rama: `chore/issue-4-monorepo-bootstrap`. PR asociado: #10; no se modificó remotamente.

## Diagnóstico inicial

- No existía `.gitignore`: entornos, cachés, SQLite y artefactos aparecían como archivos sin seguimiento.
- ASGI/WSGI ya tenían cambios locales que separaban importaciones estándar y de Django. Se preservaron; Ruff confirma que solucionan I001.
- `backend/package-lock.json` contenía `packages: {}`, nombre `backend` y ningún paquete. No existe `backend/package.json` ni una aplicación npm en backend: se confirmó como lockfile accidental y se eliminó únicamente ese archivo.
- El lockfile real del frontend estaba sin seguimiento. El workflow instalaba con `npm install`, que permite recalcular resoluciones.
- `npm audit --json` reprodujo 11 paquetes afectados: 8 moderados, 1 alto y 2 críticos. Son alertas por paquete, no 11 fallos independientes: había 16 avisos únicos, varios propagados a paquetes padres.
- Todas las rutas afectadas pertenecían a `devDependencies`. `npm audit --omit=dev` inicial reportó cero. Una herramienta de desarrollo vulnerable puede comprometer la máquina o CI aunque no se distribuya en producción.
- ESLint 9 está fuera de soporte. El entorno existente `.venv` usa Python 3.11.9; el sistema tiene Python 3.12. Se creó un entorno 3.12 temporal para validar sin alterar el existente.

## Archivos preparados

| Archivo | Cambio |
| --- | --- |
| `.gitignore` | Excluye entornos, cachés, bases locales, dependencias, compilados y configuración secreta; conserva ejemplos sanitizados y el lockfile del frontend. |
| `backend/config/asgi.py`, `backend/config/wsgi.py` | Conserva las correcciones locales de importaciones verificadas con Ruff. |
| `frontend/package.json` | Versiones explícitas de herramientas, rango de Node compatible con LTS y Vite limitado a loopback. |
| `frontend/package-lock.json` | árbol reproducible generado y verificado con `npm ci`; incluye hashes de integridad. |
| `.github/workflows/bootstrap-validation.yml` | Sustituye la instalación existente por `npm ci`; no amplía el alcance del workflow. |
| `docs/development/README.md` | Instalación reproducible, versiones de Python/Node, Ruff, auditoría y alcance del servidor local. |
| `docs/development/issue-4-validation.md` | Este diagnóstico, análisis individual, resultados reales y pendientes. |

## Dependencias

| Dependencia directa de desarrollo | Antes | Después | Motivo |
| --- | --- | --- | --- |
| vite | 7.2.2 | 7.3.8 | Parches de seguridad en la misma versión mayor; rama 7.3 con backports oficiales. |
| vitest | 3.2.4 | 4.1.12 | Corrige UI/mocker y elimina tinypool. 3.2.7 conserva dependencias afectadas; no basta ese parche. |
| eslint | 9.39.1 | 10.14.0 | Rama con soporte; evita permanecer en ESLint 9 EOL. |
| @eslint/js | 9.39.1 | 10.0.1 | Configuración compatible con ESLint 10. |
| typescript-eslint | 8.46.3 | 8.72.2 | Soporte declarado de ESLint 10; sigue afectado transitivamente por minimatch. |
| eslint-plugin-react-hooks | 7.0.1 | 7.1.1 | Peer dependency compatible con ESLint 10. |

Se mantuvieron React 19.2.0, TypeScript 5.9.3 y los requisitos Python existentes.
Se revisaron las guías de migración de ESLint 10 y Vitest 4; la configuración mínima actual funciona sin cambios adicionales. No se usaron `--force`, `--legacy-peer-deps`, overrides mayores ni exclusiones de auditoría.
La primera instalación conjunta fue rechazada por ERESOLVE al intentar resolver los peers anteriores de ESLint; se corrigió actualizando primero TypeScript ESLint/hooks y después ESLint/@eslint/js, conservando la resolución normal de npm.

## Seguridad: avisos iniciales, uno por uno

La relevancia es una evaluación del código/configuración actuales, no una prueba de explotación ni una garantía sobre dependencias futuras.

| Aviso | Paquetes con aviso directo | Gravedad del aviso | Problema | Resultado y contexto |
| --- | --- | --- | --- | --- |
| [GHSA-82fw-gwwq-j7x9](https://github.com/advisories/GHSA-82fw-gwwq-j7x9) | @vitest/mocker, vitest | moderate | Vitest: Path Traversal / Arbitrary File Read via @vitest/mocker Redirect Mock | Corregida. Redirecciones de mocks en servidor/browser mode; no se usa ese modo. |
| [GHSA-qxg6-89mg-rqv8](https://github.com/advisories/GHSA-qxg6-89mg-rqv8) | @vitest/mocker | moderate | Vitest: Code injection via unauthenticated manual mock registration | Corregida. Registro de mocks por servidor accesible y condiciones de interacción; no se usa browser mode. |
| [GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249) | minimatch | moderate | minimatch has potential denial of service via globparts amplification | Pendiente. DoS al procesar patrones glob hostiles; patrones locales controlados por el repositorio, sin entrada de usuarios del SaaS. |
| [GHSA-5gmw-xhrv-c9v3](https://github.com/advisories/GHSA-5gmw-xhrv-c9v3) | tinypool | critical | Tinypool: Prototype Pollution gadget in worker options leads to Remote Code Execution | Eliminada la dependencia tinypool. RCE condicionada a contaminación previa del prototipo; riesgo para desarrolladores/CI. |
| [GHSA-85c8-ppgw-ccpr](https://github.com/advisories/GHSA-85c8-ppgw-ccpr) | tinypool | critical | Tinypool: Prototype Pollution Gadget to RCE in run() options | Eliminada la dependencia tinypool. RCE mediante opciones heredadas y contaminación previa del prototipo; no se encontró una fuente de esa contaminación en el código propio. |
| [GHSA-4w7w-66w2-5vf9](https://github.com/advisories/GHSA-4w7w-66w2-5vf9) | vite | moderate | Vite Vulnerable to Path Traversal in Optimized Deps `.map` Handling | Corregida. Lectura por traversal en mapas de dependencias del servidor de desarrollo; exposición a red era relevante. |
| [GHSA-v2wj-q39q-566r](https://github.com/advisories/GHSA-v2wj-q39q-566r) | vite | high | Vite: `server.fs.deny` bypassed with queries | Corregida. Evasión de server.fs.deny mediante consultas al servidor de desarrollo. |
| [GHSA-p9ff-h696-f583](https://github.com/advisories/GHSA-p9ff-h696-f583) | vite | high | Vite Vulnerable to Arbitrary File Read via Vite Dev Server WebSocket | Corregida. Lectura de archivos mediante WebSocket del servidor de desarrollo accesible. |
| [GHSA-v6wh-96g9-6wx3](https://github.com/advisories/GHSA-v6wh-96g9-6wx3) | vite | moderate | launch-editor: NTLMv2 hash disclosure via UNC path handling on Windows | Corregida. Divulgación de hash NTLMv2 por rutas UNC en Windows; relevante al entorno local. |
| [GHSA-698v-4r3x-3vcv](https://github.com/advisories/GHSA-698v-4r3x-3vcv) | vite | moderate | launch-editor: escapeCmdArgs() omits % escaping on Windows | Corregida. Escape de argumentos de editor en Windows; requiere la ruta de apertura del editor. |
| [GHSA-r825-w8mm-5pxw](https://github.com/advisories/GHSA-r825-w8mm-5pxw) | vite | moderate | launch-editor: Editor CLI flag misinterpretation causing arbitrary command execution for some editors | Corregida. Interpretación de flags del editor; condicionada al editor y a la ruta de apertura. |
| [GHSA-587h-7wmj-h5pm](https://github.com/advisories/GHSA-587h-7wmj-h5pm) | vite | high | launch-editor: `fs.existsSync()` existence check can be bypassed on Windows | Corregida. Evasión de comprobación de archivo y ejecución de comandos en Windows mediante apertura de editor. |
| [GHSA-9jrq-w75r-8gcw](https://github.com/advisories/GHSA-9jrq-w75r-8gcw) | vite | low | Vite: Cross origin script execution through Vite custom middleware | Corregida. Ejecución de script cross-origin con middleware personalizado; el proyecto no configura middleware propio. |
| [GHSA-rq7h-c2jc-7f22](https://github.com/advisories/GHSA-rq7h-c2jc-7f22) | vite | moderate | Vite: Files outside `server.fs.allow` could be served when project paths match system paths on non-Windows machine | Corregida. Archivos fuera de server.fs.allow por coincidencias de rutas en sistemas no Windows; relevante para colaboradores Linux/CI. |
| [GHSA-fx2h-pf6j-xcff](https://github.com/advisories/GHSA-fx2h-pf6j-xcff) | vite | moderate | vite: `server.fs.deny` bypass on Windows alternate paths | Corregida. Evasión de server.fs.deny por rutas alternativas en Windows; relevante al entorno local. |
| [GHSA-5xrq-8626-4rwp](https://github.com/advisories/GHSA-5xrq-8626-4rwp) | vitest | critical | When Vitest UI server is listening, arbitrary file can be read and executed | Corregida. Requiere servidor UI/API de Vitest; el proyecto ejecuta vitest run sin UI. |

Los 11 paquetes iniciales señalados eran: `vite`, `vitest` y `typescript-eslint` (directos de desarrollo); `@vitest/mocker`, `tinypool`, `minimatch`, `@typescript-eslint/eslint-plugin`, `@typescript-eslint/parser`, `@typescript-eslint/type-utils`, `@typescript-eslint/typescript-estree` y `@typescript-eslint/utils` (transitivos de desarrollo).

## Pendiente justificado: minimatch

Resultado final de `npm audit`: **10 moderadas, 0 altas, 0 críticas; código de salida 1**. Queda un aviso único, GHSA-g3hv-75wg-m249, propagado a diez paquetes:

`@eslint/config-array`, `@eslint/js`, `@typescript-eslint/eslint-plugin`, `@typescript-eslint/parser`, `@typescript-eslint/type-utils`, `@typescript-eslint/typescript-estree`, `@typescript-eslint/utils`, `eslint`, `minimatch`, `typescript-eslint`.

`minimatch@10.2.6` es compartido por ESLint, `@eslint/config-array` y TypeScript ESLint. El parche del aviso está en 11.0.1; los rangos publicados requieren `^10.2.6`, `^10.2.4` y `^10.2.2`, respectivamente. Forzar 11 cambia una dependencia mayor fuera del contrato de sus consumidores. No se aplicó. La recomendación automática de npm retrocede ESLint a 9.39.5 (EOL) y TypeScript ESLint a 8.36.0; no es una solución adecuada de mantenimiento.

El aumento de alertas moderadas frente a las 8 iniciales se debe a la propagación del mismo aviso a ESLint 10, @eslint/js y @eslint/config-array; desaparece a la vez el aviso de mocker. No implica diez nuevas vulnerabilidades independientes.
El proyecto no acepta patrones glob de usuarios remotos: el riesgo actual exige introducir patrones maliciosos en la configuración/código de desarrollo. Revisar cambios de configuración y dependencias; no ejecutar contribuciones no confiables con secretos de CI. Esperar versiones de los consumidores que admitan el parche y repetir instalación, auditoría y pruebas. Esta deuda queda visible: no se cambió el nivel de auditoría ni se suprimió el aviso.

`npm audit --omit=dev` final: **0 vulnerabilidades, código 0**. Esto cubre el árbol npm de producción conocido por el registro; no certifica el backend Python ni la seguridad completa de la aplicación.

## Comprobaciones ejecutadas

Backend desde `backend`, con Python 3.12.10 y requisitos instalados en un entorno temporal independiente:

| Comando | Resultado real |
| --- | --- |
| `python manage.py check` | Código 0; sin incidencias. |
| `python -m pytest -q` | Código 0; 1 prueba aprobada (endpoint health). |
| `python -m ruff check .` | Código 0; All checks passed. |

Los mismos tres comandos pasaron también con el Python 3.11.9 del entorno existente. No se reemplazó ese entorno.

Frontend desde `frontend`, con **Node 22.23.5 LTS y npm 11.6.2**, después de una instalación reproducible:

| Comando | Resultado real |
| --- | --- |
| `npm ci` | Código 0; instalación desde lockfile, sin avisos de ESLint obsoleto ni conflictos de peers; muestra las 10 alertas moderadas pendientes. |
| `npm run lint` | Código 0. |
| `npm test` | Código 0; 1 archivo y 1 prueba aprobados. |
| `npm run build` | Código 0; TypeScript y Vite compilaron, 29 módulos transformados. |
| `npm audit` | Código 1; 10 moderadas documentadas. No se declara aprobado. |
| `npm audit --omit=dev` | Código 0; cero vulnerabilidades conocidas en producción. |
| `npm ls --depth=0` | Código 0; sin dependencias inválidas. |

Lint, test y build pasaron también con Node 25.2.1. El ensayo frontend existente comprueba que App exporta una función; no demuestra interacción de usuario ni cobertura funcional. No se añadieron funcionalidades comerciales.

Arranque real mediante subprocesos y peticiones HTTP:

- Django: `python manage.py runserver 127.0.0.1:58775 --noreload`; `/health/` respondió 200 y `{"status":"ok"}`.
- Vite con Node 22: `node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 58778 --strictPort`; `/` y `/src/main.tsx` respondieron 200 (HTML y módulo transformado).
- Ambos procesos fueron terminados en bloques de limpieza; se verificó que sus puertos ya no responden. No se dejaron servidores de esta validación activos.

## Git y revisión de secretos

Se inspeccionaron rama, estado y diferencias antes de modificar. Se preservaron los cambios locales de ASGI/WSGI. `git check-ignore -v` confirmó las exclusiones de los temporales reportados y de `.env`/`.env.local`; `frontend/package-lock.json` no está ignorado.
Solo se preparan los ocho archivos de la tabla anterior. La eliminación del lockfile accidental no genera un cambio de Git porque nunca estuvo versionado.
No se hacen commit, push, merge ni cambios en el PR #10.

La configuración contiene una clave explícitamente insegura de desarrollo (`dev-only-insecure-change-me`), no una credencial real. No se encontraron credenciales reales en la revisión del contenido preparado ni en el escaneo por patrones. El escaneo no sustituye una auditoría de todo el historial. El estado de Git no incluye entornos, bases de datos, node_modules ni dist. `git diff --check` y `git diff --cached --check` pasan.

## Conceptos para una entrevista

- `.gitignore` actúa sobre archivos sin seguimiento; no elimina del índice archivos ya versionados. Un lockfile forma parte del código reproducible, mientras node_modules es un resultado regenerable.
- `package.json` expresa requisitos; `package-lock.json` fija resoluciones transitivas e integridad; `npm ci` rechaza inconsistencias y reinstala ese árbol.
- Una dependencia directa se declara en el proyecto; una transitiva llega a través de ella. Un solo aviso transitivo puede generar numerosas entradas en audit.
- Gravedad y explotabilidad son conceptos distintos: dependen del dato controlado por el atacante, del modo de ejecución y de la exposición. Las dependencias de desarrollo también ejecutan código con los permisos del desarrollador o de CI.
- SemVer mayor exige revisar compatibilidad. Un contador menor en audit no justifica degradar herramientas a una rama EOL o forzar contratos transitivos.
- Ruff valida convenciones de Python; pytest valida comportamiento; ESLint inspecciona JS/TS; TypeScript y Vite validan compilación. Un arranque HTTP verifica una ruta adicional y no equivale a pruebas completas.
- Se conserva el monorepo con monolito modular Django/DRF + React/TypeScript/Vite, PostgreSQL como destino y SQLite solo para smoke local. No se añadieron autenticación ni módulos de negocio. El aislamiento multiempresa y la autenticación futura no quedan probados por este bootstrap.

## Referencias consultadas

- [Soporte de versiones ESLint](https://eslint.org/version-support/).
- [Migración ESLint 10](https://eslint.org/docs/latest/use/migrate-to-10.0.0).
- [Migración Vitest 4](https://v4.vitest.dev/guide/migration.html).
- [Ramas soportadas de Vite](https://vite.dev/releases).
- Avisos oficiales enlazados individualmente en la tabla; metadatos/rangos de paquetes consultados con `npm view` y árbol verificado con `npm ls`.
