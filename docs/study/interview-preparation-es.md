# Preparación para entrevistas Junior Full Stack

Este es un MVP local de portafolio, asistido por IA. El objetivo es explicar y
modificar el código con criterio. Leerlo no sustituye ejecutar los ejercicios.
Las rutas de archivos siguientes son relativas a la raíz del repositorio.
La evidencia y las limitaciones reales están en [el progreso](../development/mvp-progress.md).

## 1. Django REST Framework

**Idea:** DRF ayuda a construir APIs HTTP con serializers, vistas, permisos y respuestas.
**Código:** `backend/sales/api.py`, `SaleInput`, `SaleList`; hereda de `BusinessView`
y finalmente de `IdentityAPIView` en `backend/identity/views.py`.
**Pregunta:** ¿Qué aporta un serializer?
**ES:** Valida y transforma entradas; también convierte objetos en datos JSON.
`SaleInput` limita los items y rechaza campos desconocidos mediante StrictSerializer.
**EN:** A serializer validates input and converts Python objects into response data.
Our sale serializer rejects unknown fields and invalid quantities.
**Ejercicio sin IA:** añade un caso de prueba para una venta con dos variantes repetidas.

## 2. API REST

**Idea:** Una interfaz organiza recursos y operaciones mediante URLs y métodos HTTP.
**Código:** `backend/sales/urls.py`, `sales/` GET/POST y `sales/<uuid:pk>/` GET.
**Pregunta:** ¿Diferencia entre GET y POST?
**ES:** GET consulta sin cambiar el negocio. POST crea una venta con efectos en stock.
Nuestra cancelación es una acción POST explícita y no elimina historial.
**EN:** GET reads a resource. POST creates a sale and changes stock. We keep the
original sale when it is cancelled.
**Ejercicio:** usa curl con una cookie de sesión para consultar sales/ y explica 401/403/404.

## 3. Solicitud de React a PostgreSQL

**Idea:** El formulario produce JSON; la API autoriza, valida y ejecuta SQL; vuelve JSON.
**Código:** `frontend/src/App.tsx` → `api` en `api.ts` → proxy `frontend/vite.config.ts`
→ `SaleList.post` → `create_sale` en `backend/sales/services.py` → ORM/PostgreSQL.
**Pregunta:** ¿Dónde se calcula el total?
**ES:** En el servidor con precios del catálogo y Decimal. El navegador no decide el precio.
**EN:** The server calculates the total using current catalog prices and Decimal.
The browser only sends variant IDs and quantities.
**Ejercicio:** sigue el POST sales/ en Network y localiza el serializer y el servicio.

## 4. Autenticación y autorización

**Idea:** Autenticar identifica a alguien; autorizar decide qué puede hacer.
**Código:** `backend/identity/views.py`, `LoginView`; `backend/identity/services.py`,
`organization_for_user`; `backend/inventory/services.py`, `adjust_stock`.
**Pregunta:** ¿Por qué ocultar un botón no protege una API?
**ES:** Se puede enviar HTTP fuera de React. El servicio exige ADMIN aunque no exista botón.
**EN:** Hiding a button is only a UI decision. The backend must check the user's role
because a client can send requests directly.
**Ejercicio:** prueba un ajuste como STAFF y comprueba que no se creó un movimiento.

## 5. CSRF

**Idea:** Evita que otro sitio use automáticamente nuestras cookies para ejecutar cambios.
**Código:** `IdentityAPIView` usa csrf_protect; `frontend/src/api.ts`, `refreshCsrf`
y `api`, envían X-CSRFToken. El token se renueva tras login/registro.
**Pregunta:** ¿Por qué usar token si ya hay sesión?
**ES:** El navegador adjunta cookies; el token y la comprobación de origen distinguen
una petición autorizada del sitio de otra inducida desde un origen ajeno.
**EN:** Browsers send session cookies automatically. A CSRF token and origin checks
protect state-changing requests from another website.
**Ejercicio:** elimina X-CSRFToken en una petición de prueba y verifica 403.

## 6. Aislamiento multiempresa

**Idea:** Cada petición obtiene su organización de la membresía autenticada.
**Código:** `organization_for_user`, `BusinessView`, `locked_variant` y la migración
`backend/inventory/migrations/0003_tenant_integrity.py`.
**Pregunta:** ¿Un UUID protege por sí solo los datos?
**ES:** No. Un UUID identifica una fila; hay que filtrar por organización y comprobar
las relaciones. Las FKs compuestas impiden relaciones inconsistentes, no son RLS.
**EN:** A UUID is an identifier, not authorization. We scope queries by organization
and use composite foreign keys for relational tenant consistency.
**Ejercicio:** crea dos organizaciones y solicita una venta ajena; debe devolver 404.

## 7. Foreign Keys

**Idea:** Una FK exige que la fila referenciada exista. Una FK compuesta comprueba una pareja.
**Código:** `SaleItem.variant` en `backend/sales/models.py`; `RELATIONS` en la migración
de inventario añade `(variant_id, organization_id)` → variante `(id, organization_id)`.
**Pregunta:** ¿Basta una FK normal para impedir mezclar empresas?
**ES:** No, prueba existencia pero no igualdad de organización. La pareja añade esa condición.
**EN:** A normal foreign key proves that the row exists. A composite tenant key also
checks that both rows belong to the same organization.
**Ejercicio:** lee `test_postgres_composite_tenant_foreign_keys` y explica el rollback.

## 8. Transacciones

**Idea:** Agrupan escrituras que deben confirmarse o revertirse juntas.
**Código:** `@transaction.atomic` en `create_sale`, `adjust_stock` y `cancel_sale`.
**Pregunta:** ¿Qué filas cambian al vender?
**ES:** La venta, sus items, los balances y los movimientos. Se confirman juntos.
**EN:** A sale writes the sale record, items, balances and movements in one transaction.
If stock is insufficient, the transaction rolls back.
**Ejercicio:** provoca stock insuficiente en un item y comprueba todas las tablas.

## 9. Atomicidad

**Idea:** Es la propiedad de todo o nada; no queda media operación confirmada.
**Código:** `test_adjustment_bounds_and_atomic_insufficient_sale` en
`backend/inventory/tests/test_commerce.py`.
**Pregunta:** ¿Atomicidad evita por sí sola toda condición de carrera?
**ES:** No. Además necesitamos restricciones y bloqueos para coordinar operaciones concurrentes.
**EN:** Atomicity prevents partial changes. It does not solve every race condition;
we also need constraints and locks.
**Ejercicio:** explica qué pasaría si el movimiento se creara fuera de atomic.

## 10. SELECT FOR UPDATE y bloqueos

**Idea:** Una transacción bloquea filas para que otra espere antes de cambiarlas.
**Código:** `locked_variant`, `locked_balance` en `backend/inventory/services.py`;
orden por UUID en `create_sale` y `cancel_sale`.
**Pregunta:** ¿Cómo se bloquea un balance que aún no existe?
**ES:** Primero se bloquea la variante existente y bajo ese lock se crea el balance.
También reutilizamos el lock por organización, una limitación de throughput aceptada para el MVP.
**EN:** We lock the existing variant before creating its first balance. This prevents
two initial adjustments from creating competing rows. We also serialize tenant writes.
**Ejercicio:** dibuja la secuencia de dos ventas sobre la última unidad.

## 11. Condiciones de carrera

**Idea:** El resultado depende de cómo se intercalan solicitudes simultáneas.
**Código:** `test_concurrent_stock_operations`, con ThreadPoolExecutor y Barrier,
en `backend/inventory/tests/test_commerce.py` (solo PostgreSQL).
**Pregunta:** ¿Qué problema evita el lock al vender la última unidad?
**ES:** Impide que ambas solicitudes lean uno y confirmen dos ventas sobre la misma unidad.
**EN:** Without locking, both requests could read one available unit and both sell it.
Our PostgreSQL test expects one success and one conflict.
**Ejercicio:** ejecuta esa prueba con PostgreSQL y explica por qué SQLite la omite.

## 12. Índices

**Idea:** Estructuras que aceleran búsquedas; los índices únicos también impiden duplicados.
**Código:** `Sale.Meta.indexes`, `StockMovement.Meta.indexes`, unicidad de variante
en `InventoryBalance`, y `catalog_sku_unique` en `backend/catalog/models.py`.
**Pregunta:** ¿Por qué no indexar todas las columnas?
**ES:** Los índices ocupan espacio y encarecen escrituras. Se eligen según consultas y restricciones.
**EN:** Indexes improve reads but cost storage and write time. We choose them for
tenant filtering, ordering and uniqueness.
**Ejercicio:** identifica el índice usado para garantizar un solo balance por variante.

## 13. Migraciones

**Idea:** Versionan cambios del esquema y sus dependencias.
**Código:** `backend/catalog/migrations/0003_productvariant_catalog_variant_tenant_key.py`,
las migraciones nuevas de inventory/sales y `scripts/verify_identity_database.py`.
**Pregunta:** ¿Por qué makemigrations --check no demuestra toda integridad?
**ES:** Compara estado de modelos, pero no prueba el comportamiento de DDL personalizado.
Ejecutamos pruebas reales y reversión/reaplicación en bases nuevas.
**EN:** Migration drift checks compare model state. Custom SQL constraints also need
real database tests and migration verification.
**Ejercicio:** localiza el guard legacy y explica por qué no debe eludirse con --fake.

## 14. Componentes y hooks de React

**Idea:** Los componentes describen la interfaz; useState mantiene estado y useEffect
sincroniza con sistemas externos.
**Código:** `App`, `Field`, `Pager`, `StockTable`, `SalesTable` en `frontend/src/App.tsx`.
El efecto inicial consulta auth/me/; los formularios llaman perform/api.
**Pregunta:** ¿Qué diferencia hay entre props y estado?
**ES:** Props son entradas del padre; estado es información local que cambia y provoca render.
**EN:** Props are inputs from a parent component. State is local data that changes
over time and triggers a render.
**Ejercicio:** añade una indicación accesible de carrito vacío sin cambiar el backend.

## 15. TypeScript

**Idea:** Detecta incompatibilidades de tipos durante desarrollo; no valida el JSON en ejecución.
**Código:** interfaces Page, Stock, Sale en `frontend/src/api.ts`; `View` en App.tsx.
**Pregunta:** ¿api<Sale> garantiza que el servidor responda con una Sale válida?
**ES:** No, es una expectativa estática. Backend y pruebas verifican el contrato real.
**EN:** TypeScript checks our code at build time. A generic type does not validate
network data at runtime, so API contracts and integration tests still matter.
**Ejercicio:** intenta asignar un string a Stock.quantity y observa el error de tsc.

## 16. Docker

**Idea:** Empaqueta procesos y dependencias en contenedores; Compose conecta servicios locales.
**Código:** `compose.yaml`, Dockerfiles, `scripts/start_identity_sandbox.py`.
**Pregunta:** ¿Por qué un contenedor nuevo no garantiza una base vacía?
**ES:** Puede adjuntar un volumen antiguo. El helper verifica un proyecto y volumen nuevos
y su montaje real antes de migrar. Nunca usamos el PostgreSQL original.
**EN:** A new container can reuse an old volume. Our sandbox checks a new project,
a new volume and the actual mount before applying migrations.
**Ejercicio:** crea un sandbox y deténlo con su compose_argv sin borrar su volumen.

## 17. GitHub Actions

**Idea:** Ejecuta comprobaciones reproducibles sobre los cambios publicados.
**Código:** `.github/workflows/bootstrap-validation.yml`: Django, React, PostgreSQL,
Compose y auditoría npm. Los cinco jobs se conservan.
**Pregunta:** ¿CI verde significa preparado para producción?
**ES:** No. Demuestra las comprobaciones ejecutadas; quedan rate limiting, verificación
de correo, recuperación, operación de producción y la revisión humana.
**EN:** Green CI proves the configured checks passed. It is not a production security
certification or a replacement for review.
**Ejercicio:** encuentra en un run el comando exacto que ejecutó PostgreSQL.

## 18. Unit tests e integration tests

**Idea:** Una prueba unitaria aísla un comportamiento; una integración combina partes reales.
**Código:** `frontend/src/api.test.ts` usa fetch controlado para probar cabeceras/rotación;
`backend/inventory/tests/test_commerce.py` usa ORM/API/DB reales; el helper Compose
hace HTTP real. `scripts/verify_mvp_transport.mjs` ejecuta api.ts real por Vite sin mockear respuestas.
**Pregunta:** ¿Una prueba de transporte es una prueba visual completa?
**ES:** No. Prueba solicitudes reales, no clicks, layout ni usabilidad. El informe distingue
el bloqueo de Computer Use de los resultados HTTP aprobados.
**EN:** A transport integration test checks real HTTP behavior. It does not prove
the whole visual user journey or responsive usability.
**Ejercicio:** clasifica tres pruebas del repositorio y explica qué no demuestran.

## 19. Depurar backend

**Idea:** Reproducir el error mínimo, revisar status/envelope/logs y localizar la primera causa.
**Código:** `backend/identity/errors.py`, `api_exception_handler`; `change_stock` lanza
Conflict; `SaleList.post` valida SaleInput antes del servicio.
**Pregunta:** ¿Cómo investigar un 409 al vender?
**ES:** Revisaría stock, disponibilidad e items, reproduciría en el sandbox y comprobaría
que no persistieron efectos parciales. No desactivaría controles ni registraría secretos.
**EN:** I would inspect the response, available stock and input, reproduce it in the
sandbox, then check that the failed transaction left no partial records.
**Ejercicio:** provoca un 400 y un 409, y explica sus causas distintas.

## 20. Explicar el proyecto

**Idea:** Cuenta un flujo concreto, una decisión defendible y un límite honesto.
**Código:** `create_sale`, `change_stock`, api.ts, tests PostgreSQL y README.
**Pregunta:** ¿Qué hiciste con IA y qué puedes explicar por tu cuenta?
**ES:** Usé IA para acelerar implementación, pruebas y documentación. Debo poder seguir
el flujo, explicar locks/CSRF/aislamiento y modificar una prueba sin IA. No afirmo
dominar partes que todavía no he estudiado ni presentar esto como SaaS comercial.
**EN:** I used AI tools to accelerate implementation, testing and documentation.
I can explain the request flow and the decisions I have personally reviewed.
I am still learning and would ask for review when a change exceeds my understanding.
**Ejercicio:** explica create_sale en voz alta y cambia una validación con su prueba sin IA.

## Presentación de 60–90 segundos en inglés

“This is a local inventory and sales MVP built with React, TypeScript, Django REST
Framework and PostgreSQL. A user signs in, creates a product with variants, adds
stock and records a sale. The server updates stock and keeps a movement history.

Each account belongs to one organization. The API checks membership and scopes
queries to that organization. Composite foreign keys also prevent inconsistent
relationships in PostgreSQL. Sessions use HttpOnly cookies, and writes require CSRF.

The most interesting part is the sale transaction. It locks variants and balances
in a consistent order, checks available stock, captures the current price and writes
the sale and movements atomically. A concurrent test checks that two sales cannot
both sell the last unit.

I used AI tools to help implement, test and document the project. My responsibility
is to understand the code, verify the results and explain the tradeoffs. This is a
portfolio demo, not production software. Email verification, recovery and abuse
controls are still missing, and the validation report describes the UI test limit.”

Practica con tus palabras. Solo afirma que puedes defender una decisión después de
estudiarla y completar su ejercicio. Nunca memorices resultados como sustituto de comprensión.
