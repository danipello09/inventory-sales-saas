# Stockroom — presentación de portafolio y plan de entrevistas

> Proyecto local de aprendizaje y portafolio, desarrollado con asistencia de IA.
> No es un despliegue comercial ni una aplicación lista para producción.

## Descripción breve para CV y LinkedIn (español)

**Stockroom — Inventory & Sales Management MVP**. Aplicación Full Stack local con React, TypeScript, Django REST Framework y PostgreSQL. Permite gestionar categorías, productos y variantes, registrar ajustes de inventario, realizar ventas con descuento transaccional de existencias, consultar historial y cancelar ventas con reposición idempotente. Incluye autenticación con sesiones y CSRF, permisos ADMIN/STAFF, separación de organizaciones y pruebas automatizadas con GitHub Actions. Desarrollo asistido por IA, con revisión de arquitectura y validación funcional y de seguridad.

## Portfolio description (English)

**Stockroom — Inventory & Sales Management MVP** is a local full-stack portfolio application built with React, TypeScript, Django REST Framework and PostgreSQL. It supports product catalogs, stock adjustments, sales with transactional inventory updates, movement history and safe sale cancellations. It uses session authentication, CSRF protection, organization-scoped permissions, PostgreSQL integrity constraints and CI tests. AI tools assisted the implementation; I focus on understanding, validating and explaining the technical decisions.

## Pitch de 60–90 segundos (inglés intermedio)

> I built Stockroom, an inventory and sales management MVP, as a full-stack portfolio project. The frontend uses React and TypeScript, while Django REST Framework provides the API and PostgreSQL stores the business data. Users can create products, add stock, record sales and track movements. When a sale is created, the backend validates the request, checks stock availability and updates the database inside a transaction. This prevents partial sales when an operation fails. The system also supports different organizations and user roles, so each organization can access only its own data. I used Docker for a reproducible local environment and GitHub Actions to run automated checks. I used AI tools to accelerate implementation, but my learning goal is to understand the architecture, explain the trade-offs and solve issues independently. This is a local MVP, not a production-ready commercial system.

## Demostración grabada de 2–3 minutos

Solo utilizar datos sintéticos y la **URL del nuevo sandbox local**. No incluir contraseñas, secretos, cookies, archivos privados ni datos reales.

| Tiempo | Mostrar | Explicar |
| --- | --- | --- |
| 0:00–0:20 | Login y pantalla inicial | React, TypeScript, sesiones y CSRF |
| 0:20–0:50 | Categoría, producto y variante de precio 12.50 | Modelos, API REST, UUID y validación |
| 0:50–1:15 | Ajuste +10 e historial | StockMovement, autorización ADMIN y transacciones |
| 1:15–1:50 | Venta de 3, total 37.50, saldo 7 | Decimal, atomicidad y bloqueos |
| 1:50–2:10 | Historial, precio histórico y cancelación opcional | Trazabilidad e idempotencia |
| 2:10–2:35 | Organización distinta con listas vacías | Aislamiento multiempresa; 404 para recursos ajenos |
| 2:35–3:00 | Código fuente y GitHub Actions | Servicios Django, PostgreSQL y CI; límites de producción |

### Capturas para portafolio

Tomar capturas reales, no generadas ni simuladas, de: (1) catálogo con variantes, (2) inventario con saldo y movimientos, (3) venta con total y detalle, (4) vista responsive. Verificar que no aparezcan contraseñas, emails personales, cookies ni IDs privados. Subirlas después de revisarlas; este documento no afirma que ya existan.

## Ruta de estudio: 7 sesiones

1. **API y HTTP** — seguir `frontend/src/api.ts` → `backend/sales/api.py`. Explicar GET/POST, 400/401/403/404/409, JSON y serializers.
2. **Python y Django** — recorrer `backend/sales/services.py` y `backend/inventory/services.py`. Identificar funciones, ORM, excepciones y responsabilidades.
3. **SQL y transacciones** — estudiar tablas, FKs, JOIN, índices y `transaction.atomic`. Explicar una venta con stock insuficiente.
4. **Seguridad** — `backend/identity/views.py`, `backend/identity/services.py` y `frontend/src/api.ts`. Distinguir autenticación, autorización, sesiones y CSRF.
5. **React y TypeScript** — `frontend/src/App.tsx` y `frontend/src/api.ts`. Explicar estado, hooks, formularios, fetch y límites del tipado estático.
6. **Git, Docker y CI** — `compose.yaml`, `.github/workflows/bootstrap-validation.yml` y `scripts/start_identity_sandbox.py`. Explicar contenedores, volúmenes y checks.
7. **Entrevista simulada** — presentar Stockroom en inglés durante 90 segundos, responder preguntas de cada sesión y resolver una modificación pequeña sin IA.

Usar la [guía completa](interview-preparation-es.md) para ejemplos reales, respuestas ES/EN y ejercicios. Cada sesión debe cerrar con tres tareas: explicar un concepto sin leer, encontrarlo en el código y resolver una pregunta práctica.

## Preguntas de defensa esenciales

1. ¿Por qué no basta con ocultar un botón a un usuario STAFF?
2. ¿Qué diferencia existe entre una sesión y un token CSRF?
3. ¿Qué pasa si falla el descuento de la segunda variante al registrar una venta?
4. ¿Por qué usamos Decimal en lugar de float para precios?
5. ¿Qué evita `select_for_update` cuando dos solicitudes venden la última unidad?
6. ¿Qué garantiza una FK compuesta por ID y organización, y qué no garantiza?
7. ¿Cómo se ejecuta un sandbox nuevo sin reutilizar la base legacy?
8. ¿Qué no demuestra tener CI verde?
9. ¿Qué parte del código modificarías para agregar un nuevo campo de producto?
10. ¿Qué partes asistió la IA y qué puedes explicar y modificar por tu cuenta?

## Límites y honestidad profesional

El MVP funciona localmente, con pruebas PostgreSQL y validación manual del recorrido principal. No está disponible públicamente ni incluye rate limiting, verificación de email, recuperación de cuenta o configuración completa para producción. SQLite no demuestra los bloqueos y restricciones específicos de PostgreSQL. Algunas operaciones POST no tienen claves de idempotencia: si se pierde la respuesta, consultar historial antes de reintentar.

Última integración del MVP: [PR #18](https://github.com/danipello09/inventory-sales-saas/pull/18).
