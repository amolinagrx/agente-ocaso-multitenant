# API REST Ocaso Gestion v1.0

API REST para integrar la aplicacion Ocaso Gestion con sistemas externos (agentes IA, Zapier, PowerBI, etc.).

**Base URL por subdominio**: `https://oficina1.gestion.ocasoarmilla.es`

**Fallback por path**: `https://gestion.ocasoarmilla.es/oficina1`

---

## Autenticacion

Todas las peticiones (excepto `/v1/health`) requieren autenticacion mediante **API Key**.

### Obtener una API Key

1. Accede a **Ajustes > API Keys**
2. Introduce un nombre descriptivo (ej: "Zapier", "IA Agent")
3. Pulsa **Generar**
4. Copia el token generado

### Uso

Incluye el token en cada peticion mediante el header HTTP:

```
X-API-Key: tu-token-aqui
```

La API key y la URL deben pertenecer al mismo tenant. No se acepta `tenant_id` del cliente como fuente de autoridad.

### Revocar

Desde **Ajustes > API Keys**, pulsa **Revocar** en la key que quieras desactivar.

### Seguridad

- Cada API Key está vinculada a un usuario y tenant
- Hereda los permisos de ese usuario
- Se registra la fecha del ultimo uso
- Tokens de 64 caracteres hexadecimales

---

## Endpoints

### Health Check

```http
GET /v1/health
```

**Sin autenticacion**. Verifica que el servicio esta operativo.

**Respuesta**:
```json
{
  "status": "ok",
  "version": "1.0",
  "timestamp": "2026-07-28T10:00:00"
}
```

---

### Busqueda Unificada

```http
GET /v1/search?q={texto}
```

Busca en clientes, polizas y siniestros. Ideal para agentes de IA.

**Parametros**:
| Param | Tipo | Descripcion |
|---|---|---|
| `q` | string | Texto a buscar (min 2 caracteres) |

**Respuesta**:
```json
{
  "results": [
    {
      "type": "cliente",
      "id": 1,
      "nombre": "Antonio Garcia",
      "dni": "12345678A",
      "telefono": "958123456",
      "polizas_activas": 3,
      "url": "/clientes/1"
    },
    {
      "type": "poliza",
      "id": 5,
      "numero_poliza": "OC-AU-100004",
      "ramo": "auto",
      "cliente_nombre": "Antonio Garcia",
      "cliente_id": 1,
      "url": "/polizas/"
    }
  ],
  "total": 2
}
```

**Ejemplo**:
```bash
curl -H "X-API-Key: TOKEN" "http://localhost:5050/v1/search?q=garcia"
```

---

### Estadisticas

```http
GET /v1/stats
```

Estadisticas generales de la plataforma.

**Respuesta**:
```json
{
  "clientes_total": 50,
  "polizas_activas": 166,
  "polizas_mes": 5,
  "recibos_pendientes": 23,
  "siniestros_abiertos": 4,
  "leads_activos": 8,
  "timestamp": "2026-07-28T10:00:00"
}
```

---

### Mi Perfil

```http
GET /v1/me
```

Informacion del usuario asociado a la API Key.

**Respuesta**:
```json
{
  "user_id": 1,
  "username": "admin",
  "is_admin": true
}
```

---

## Clientes

### Listar Clientes

```http
GET /v1/clientes
```

**Parametros**:
| Param | Tipo | Default | Descripcion |
|---|---|---|---|
| `page` | int | 1 | Numero de pagina |
| `per_page` | int | 50 | Resultados por pagina (max 200) |
| `buscar` | string | - | Busqueda por nombre, DNI o telefono |

**Respuesta**:
```json
{
  "total": 50,
  "page": 1,
  "per_page": 50,
  "data": [
    {
      "id": 1,
      "nombre": "Antonio Garcia",
      "dni": "12345678A",
      "telefono": "958123456",
      "email": "antonio@email.com",
      "direccion": "C/ Real 15, Armilla",
      "codigo_postal": "18100",
      "poblacion": "Armilla",
      "provincia": "Granada",
      "fecha_alta": "2025-01-15T10:30:00",
      "alerta_devoluciones": false
    }
  ]
}
```

**Ejemplo**:
```bash
curl -H "X-API-Key: TOKEN" "http://localhost:5050/v1/clientes?buscar=garcia&page=1"
```

---

### Ver Cliente

```http
GET /v1/clientes/{id}
```

Incluye las polizas activas del cliente.

**Respuesta**: Igual que listar, pero con campo `polizas` incluido.

```json
{
  "id": 1,
  "nombre": "Antonio Garcia",
  ...
  "polizas": [
    {
      "id": 5,
      "numero_poliza": "OC-AU-100004",
      "ramo": "auto",
      "compania": "Ocaso",
      "prima_anual": 450.0,
      ...
    }
  ]
}
```

---

### Crear Cliente

```http
POST /v1/clientes
```

**Body** (JSON):
```json
{
  "nombre": "Nuevo Cliente",
  "dni": "87654321B",
  "telefono": "600111222",
  "email": "cliente@email.com",
  "direccion": "Avda. Principal 10",
  "codigo_postal": "18001",
  "poblacion": "Granada",
  "provincia": "Granada",
  "notas": "Cliente captado por web"
}
```

**Campos requeridos**: `nombre`

**Respuesta**: `201 Created` con el objeto cliente creado.

**Ejemplo**:
```bash
curl -X POST -H "X-API-Key: TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"nombre":"Nuevo","telefono":"600111222"}' \
  http://localhost:5050/v1/clientes
```

---

### Actualizar Cliente

```http
PUT /v1/clientes/{id}
```

**Body** (JSON): Campos a modificar (solo los incluidos se actualizan).

```json
{
  "telefono": "600999888",
  "email": "nuevo@email.com",
  "notas": "Actualizado por API"
}
```

**Respuesta**: `200 OK` con el objeto actualizado.

---

### Eliminar Cliente

```http
DELETE /v1/clientes/{id}
```

Elimina el cliente y todos sus datos asociados (polizas, recibos, siniestros, documentos).

**Respuesta**: `200 OK`
```json
{ "deleted": true }
```

---

### Documentos de Cliente

#### Listar Documentos

```http
GET /v1/clientes/{id}/documentos
```

**Respuesta**:
```json
[
  {
    "id": 1,
    "nombre": "poliza_escaneada.pdf",
    "tipo": "poliza"
  }
]
```

#### Subir Documento

```http
POST /v1/clientes/{id}/documentos
```

**Content-Type**: `multipart/form-data`

**Campos**:
| Campo | Tipo | Descripcion |
|---|---|---|
| `documento` | file | Archivo a subir |
| `tipo` | string | Tipo (poliza, dni, certificado, escaneo, otro) |

**Ejemplo**:
```bash
curl -X POST -H "X-API-Key: TOKEN" \
  -F "documento=@poliza.pdf" \
  -F "tipo=poliza" \
  http://localhost:5050/v1/clientes/1/documentos
```

**Respuesta**: `201 Created`
```json
{
  "id": 2,
  "nombre": "poliza.pdf",
  "tipo": "poliza"
}
```

---

## Polizas

### Listar Polizas

```http
GET /v1/polizas
```

**Parametros**:
| Param | Tipo | Descripcion |
|---|---|---|
| `page` | int | Pagina (default 1) |
| `per_page` | int | Por pagina (max 200) |
| `ramo` | string | Filtrar por ramo |
| `activa` | string | `true` o `false` |

**Respuesta**:
```json
{
  "total": 166,
  "page": 1,
  "per_page": 50,
  "data": [
    {
      "id": 1,
      "cliente_id": 1,
      "numero_poliza": "OC-AU-100000",
      "ramo": "auto",
      "compania": "Ocaso",
      "descripcion": "Seguro de auto",
      "capital_asegurado": 50000.0,
      "prima_anual": 450.0,
      "fecha_efecto": "2025-01-01",
      "fecha_vencimiento": "2026-01-01",
      "activa": true,
      "numero_cuenta": "ES12 3456 7890 12 3456789012",
      "unidades": 1,
      "detalles": "Cobertura todo riesgo",
      "marca": "Toyota",
      "modelo": "Corolla",
      "matricula": "1234 ABC"
    }
  ]
}
```

---

### Ver Poliza

```http
GET /v1/polizas/{id}
```

---

### Crear Poliza

```http
POST /v1/polizas
```

**Body** (JSON):
```json
{
  "cliente_id": 1,
  "numero_poliza": "OC-AU-999999",
  "ramo": "auto",
  "compania": "Ocaso",
  "prima_anual": 450,
  "capital_asegurado": 50000,
  "fecha_efecto": "2026-01-01",
  "fecha_vencimiento": "2027-01-01",
  "numero_cuenta": "ES12 3456 7890 12 3456789012",
  "unidades": 1,
  "detalles": "Detalles adicionales",
  "activa": true
}
```

**Campos requeridos**: `cliente_id`, `numero_poliza`

---

### Actualizar Poliza

```http
PUT /v1/polizas/{id}
```

**Body** (JSON): Solo campos a modificar.

```json
{
  "prima_anual": 500,
  "detalles": "Actualizada cobertura"
}
```

---

### Eliminar Poliza

```http
DELETE /v1/polizas/{id}
```

**Respuesta**: `200 OK`
```json
{ "deleted": true }
```

---

## Recibos

### Listar Recibos

```http
GET /v1/recibos
```

**Parametros**:
| Param | Tipo | Descripcion |
|---|---|---|
| `page` | int | Pagina |
| `per_page` | int | Por pagina (max 200) |
| `estado` | string | cobrado / devuelto / pendiente |

**Respuesta**:
```json
{
  "total": 1800,
  "page": 1,
  "per_page": 50,
  "data": [
    {
      "id": 1,
      "cliente_id": 1,
      "numero_poliza": "OC-AU-100000",
      "concepto": "Prima Auto - Jan 2025",
      "importe": 37.50,
      "fecha_emision": "2025-01-01",
      "fecha_cargo": "2025-01-05",
      "estado": "cobrado",
      "estado_gestion": null,
      "compania": "Ocaso",
      "notas": null
    }
  ]
}
```

---

### Crear Recibo

```http
POST /v1/recibos
```

**Body** (JSON):
```json
{
  "cliente_id": 1,
  "poliza_id": 5,
  "numero_poliza": "OC-AU-100000",
  "concepto": "Prima mensual",
  "importe": 37.50,
  "fecha_emision": "2026-07-28",
  "fecha_cargo": "2026-08-01",
  "estado": "pendiente",
  "compania": "Ocaso",
  "notas": "Creado via API"
}
```

**Campos requeridos**: `cliente_id`, `importe`

---

## Siniestros

### Listar Siniestros

```http
GET /v1/siniestros
```

**Parametros**:
| Param | Tipo | Descripcion |
|---|---|---|
| `page` | int | Pagina |
| `per_page` | int | Por pagina (max 100) |

**Respuesta**:
```json
{
  "total": 12,
  "page": 1,
  "per_page": 50,
  "data": [
    {
      "id": 1,
      "cliente_id": 1,
      "poliza_id": 5,
      "numero_expediente": "EXP-2025-1000",
      "tipo": "accidente_trafico",
      "descripcion": "Colision en cruce",
      "fecha_ocurrencia": "2025-03-15",
      "fecha_apertura": "2025-03-16",
      "estado": "abierto",
      "importe_estimado": 2500.0,
      "fecha_ultima_actualizacion": "2025-03-20T10:00:00"
    }
  ]
}
```

---

### Ver Siniestro

```http
GET /v1/siniestros/{id}
```

---

### Crear Siniestro

```http
POST /v1/siniestros
```

**Body** (JSON):
```json
{
  "cliente_id": 1,
  "poliza_id": 5,
  "numero_expediente": "EXP-2026-0001",
  "tipo": "accidente_trafico",
  "descripcion": "Descripcion del siniestro",
  "fecha_ocurrencia": "2026-07-28",
  "fecha_apertura": "2026-07-28",
  "estado": "abierto",
  "importe_estimado": 1500
}
```

**Campos requeridos**: `cliente_id`, `tipo`, `numero_expediente`

---

## Leads

### Listar Leads

```http
GET /v1/leads
```

**Parametros**:
| Param | Tipo | Descripcion |
|---|---|---|
| `page` | int | Pagina |
| `per_page` | int | Por pagina (max 200) |
| `estado` | string | nuevo / contactado / presupuesto / ganado / perdido |

### Crear Lead

```http
POST /v1/leads
```

**Body** (JSON):
```json
{
  "nombre": "Prospecto Nuevo",
  "telefono": "600111222",
  "email": "lead@email.com",
  "dni": "11223344C",
  "ramo_interes": "Hogar",
  "origen": "web",
  "estado": "nuevo",
  "notas": "Interesado en seguro de hogar"
}
```

**Campos requeridos**: `nombre`

### Eliminar Lead

```http
DELETE /v1/leads/{id}
```

**Respuesta**: `200 OK`
```json
{ "deleted": true }
```

---

## Codigos de Estado HTTP

| Codigo | Significado |
|---|---|
| `200` | OK |
| `201` | Creado correctamente |
| `400` | Error en los datos enviados |
| `401` | API Key no proporcionada |
| `403` | API Key invalida o usuario desactivado |
| `404` | Recurso no encontrado |
| `500` | Error interno del servidor |

---

## Paginacion

Todos los endpoints de listado soportan paginacion:

```
GET /v1/clientes?page=2&per_page=100
```

**Respuesta incluye**:
```json
{
  "total": 250,
  "page": 2,
  "per_page": 100,
  "data": [...]
}
```

---

## Limitaciones

- **Rate limiting**: no implementado actualmente. Evitar peticiones masivas.
- **Tamaño maximo de subida**: 16MB por peticion.
- **Documentos**: maximo 10MB por archivo.
- **Resultados por pagina**: maximo 200.

---

## Ejemplos de Integracion

### Python

```python
import requests

API_URL = "http://localhost:5050"
HEADERS = {"X-API-Key": "tu-token"}

# Listar clientes
r = requests.get(f"{API_URL}/v1/clientes", headers=HEADERS)
clientes = r.json()["data"]

# Buscar
r = requests.get(f"{API_URL}/v1/search", headers=HEADERS, params={"q": "garcia"})

# Crear recibo
r = requests.post(f"{API_URL}/v1/recibos", headers=HEADERS, json={
    "cliente_id": 1,
    "importe": 150.0,
    "concepto": "Prima mensual"
})

# Subir documento
with open("poliza.pdf", "rb") as f:
    r = requests.post(
        f"{API_URL}/v1/clientes/1/documentos",
        headers=HEADERS,
        files={"documento": f},
        data={"tipo": "poliza"}
    )
```

### JavaScript (fetch)

```javascript
const API_URL = "http://localhost:5050";

// Listar clientes
const res = await fetch(`${API_URL}/v1/clientes`, {
  headers: { "X-API-Key": "tu-token" }
});
const data = await res.json();

// Crear lead
const res2 = await fetch(`${API_URL}/v1/leads`, {
  method: "POST",
  headers: {
    "X-API-Key": "tu-token",
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    nombre: "Nuevo Lead",
    telefono: "600111222",
    origen: "web"
  })
});
```
