# Catálogo multiempresa: apuntes de estudio

Este módulo añade categorías, productos y variantes al backend de identidad ya
integrado. No añade inventario, ventas ni interfaz comercial. Su diseño completo
está en [el documento técnico](../architecture/product-catalog.md).

## Modelo y decisiones

Una Category pertenece a una organización. Un Product pertenece a esa misma
organización y a una categoría. Un ProductVariant pertenece al producto y conserva
también organization_id para permitir una restricción única de SKU por empresa.
Las tres entidades tienen UUID y se desactivan mediante is_active; no hay DELETE.

Un FK normal de producto a categoría solo demuestra que la categoría existe: no
que sea de la misma empresa. En PostgreSQL añadimos una clave única `(id, organization_id)`
al padre y una FK compuesta `(category_id, organization_id)` en el hijo. Repetimos
el patrón entre variante y producto. Así un UPDATE directo por ORM que cruce
organizaciones falla en la base, aunque no pase por un serializer.

Eso es **integridad relacional**, no autorización ni RLS. La API sigue obteniendo
la organización desde la membresía del usuario, limita todas sus consultas a ella
y devuelve 404 para UUID ajenos. Un operador con acceso SQL privilegiado no queda
aislado por estas FKs al leer tablas. No se afirma lo contrario.

Los nombres de categorías son únicos ignorando mayúsculas dentro de una empresa;
pueden repetirse entre empresas. Los SKU se normalizan a mayúsculas y se reservan
incluso estando inactivos. No se reutiliza silenciosamente un código que podrá
estar vinculado con historial de inventario o ventas.

## Variante sin talla o color

Talla/color opcionales se guardan como strings vacíos, nunca NULL, y se normalizan
a minúsculas sin espacios exteriores. Una clave única `(product_id, size, color)`
impide crear dos variantes sin opciones o duplicar `M/Blue` como ` m /blue`.
El SKU identifica una variante dentro de una empresa; la combinación talla/color
define otra unicidad distinta dentro del producto. Ninguna sustituye a la otra.

## Producto completo y transacciones

El POST de producto exige entre 1 y 50 variantes y crea todas las filas en una
transacción. Si la segunda variante colisiona con un SKU existente, tampoco queda
el producto ni la primera variante. No basta validar `.exists()` antes de insertar:
dos peticiones podrían superar esa comprobación simultáneamente.

PostgreSQL aporta una última defensa con índices únicos. Las pruebas incluyen dos
ADMIN de una empresa haciendo HTTP concurrente y dos conexiones insertando el mismo
SKU sin los locks de servicio. Solo una transacción puede confirmar el código.

La regla de al menos una variante también se comprueba mediante triggers diferidos
al commit. Permite insertar primero el producto y después sus variantes dentro
de la transacción, pero rechaza confirmar el producto vacío. Al eliminar o mover
una variante mediante SQL/ORM se serializa sobre la fila del producto anterior,
de modo que dos borrados concurrentes no pueden dejarlo sin variantes. Se probaron
READ COMMITTED y REPEATABLE READ: el segundo escritor debe fallar, no violar la regla.
No se implementó una API de eliminación física ni acceso SQL público.

## Precios y estados

El precio usa Decimal(12,2), no float. El JSON lo expresa como `"12.50"`, conserva
dos decimales y rechaza NaN, Infinity, negativos, notación exponencial y precisión
excesiva. COP/USD/EUR usan la política de dos decimales del catálogo actual. La DB
mantiene escala y límites; SQL directo puede redondear a la escala declarada, mientras
la API rechaza entradas con más de dos decimales. No se afirman garantías idénticas.

Desactivar una categoría no reescribe los flags de sus productos. `is_available`
combina los estados de categoría/producto/variante; la disponibilidad de producto
considera categoría y producto. STAFF y ADMIN pueden consultar metadata inactiva,
pero crear/reactivar exige los padres activos según el contrato. El futuro servicio
de ventas deberá validar la variante efectiva, no solo el flag del producto.

## Consultas y garantías verificadas

Las listas tienen páginas de 20 por defecto y máximo 100. No se incluye una lista
ilimitada de variantes dentro de cada producto: hay un contador y un endpoint
paginado independiente. Los filtros nunca sustituyen el scoping por organización.
Las consultas usan select_related y anotación del contador para evitar consultas
por cada variante/producto al serializar una página.

SQLite ejecuta pruebas de API y restricciones portables, pero omite los FKs
compuestos y triggers diferidos específicos de PostgreSQL. Un test verde solo en
SQLite no demuestra esas garantías. Las pruebas directas PostgreSQL comprueban
incluso el nombre de la restricción que falla para no confundir una colisión de
nombre o una regla de variantes con la FK que se pretende probar.

## Preguntas para una entrevista

| Pregunta | Respuesta breve |
| --- | --- |
| ¿Por qué un UUID no garantiza aislamiento? | Identifica una fila; no demuestra que dos filas referenciadas tengan la misma organización. |
| ¿Por qué denormalizar organization_id en variante? | Permite unicidad de SKU por empresa y una FK compuesta que comprueba su coherencia con el producto. |
| ¿Para qué diferir una restricción? | Para comprobar el estado final de una transacción que crea varias filas relacionadas, no un estado intermedio incompleto. |
| ¿Basta con una transacción para evitar SKU duplicados? | No; necesita una restricción única que coordine escrituras concurrentes. |
| ¿Por qué no borrar productos? | Se conservan UUID y relaciones para el futuro historial de inventario/ventas. |
| ¿Qué no resuelve este módulo? | Stock, ventas, permisos de negocio futuros, RLS, controles de abuso ni despliegue de producción. |

Para reproducir usa el [sandbox seguro](../development/identity-cutover.md) con
`--verify --catalog`, o el verificador PostgreSQL con el Python del venv. Nunca
uses el volumen viejo de Fase 2 ni --fake. La evidencia del trabajo está en
[validación del catálogo](../development/catalog-validation.md).
