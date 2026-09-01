# Agentes Élite - Manual de Usuario

Aplicación web multi-tenant para la gestión integral de las oficinas de **Agentes Élite**. Cada oficina accede por su subdominio o prefijo de ruta y sus datos están completamente aislados (aislamiento obligatorio por tenant en acceso, ORM, datos y archivos).

Este documento describe la aplicación de forma exhaustiva para que sirva de fuente al elaborar un manual completo de presentación adaptado a cada audiencia. La documentación técnica y de despliegue está en `README.md` y `docs/`.

## Indice

1. [Instalacion y acceso](#1-instalacion-y-acceso)
2. [Dashboard](#2-dashboard)
3. [Recibos y Cobros](#3-recibos-y-cobros)
4. [Clientes](#4-clientes)
5. [Polizas](#5-polizas)
6. [Renovaciones](#6-renovaciones)
7. [Listados](#7-listados)
8. [Cartera](#8-cartera)
9. [Utilidades](#9-utilidades)
10. [Siniestros](#10-siniestros)
11. [Comunicaciones](#11-comunicaciones)
12. [WhatsApp](#12-whatsapp)
13. [Leads](#13-leads)
14. [Agenda](#14-agenda)
15. [Asistente IA](#15-asistente-ia)
16. [Portal de Clientes](#16-portal-de-clientes)
17. [Ajustes](#17-ajustes)
18. [Usuarios y Permisos](#18-usuarios-y-permisos)
19. [Seguridad (2FA)](#19-seguridad-2fa)
20. [API Externa](#20-api-externa)
21. [Copias de Seguridad](#21-copias-de-seguridad)

---

## 1. Instalacion y acceso

### Requisitos
- Docker y Docker Compose instalados

### Instalacion
```bash
git clone https://github.com/amolinagrx/agente-ocaso-multitenant.git
cd agente-ocaso-multitenant
git checkout multitenant
cp .env.example .env
# Configura secretos, tenant inicial y super-admin.
docker compose up -d --build
docker compose exec ocaso python3 scripts/seed_multitenant.py
```

### Acceso
- Oficina por path: `http://localhost:5050/{subdominio-oficina}/login` (ej. `/oficina-inicial/login`)
- Oficina por subdominio: `https://{subdominio}.gestion.ocasoarmilla.es/login`
- Super-admin (global): `http://localhost:5050/login` (sin salir de una oficina; campo "Oficina" vacío)
- No existen credenciales por defecto; se crean con variables de entorno.

### Identificación del usuario
El acceso se puede realizar con el **correo electrónico o el usuario**:
- Campo **"Correo o usuario"**: acepta tanto la dirección de email como el nombre de usuario registrado.
- Esto se aplica tanto al login global (super-admin) como al de cada oficina.

### Cambiar de oficina
- Tras hacer logout, permaneces en la pantalla de login de la oficina desde la que has salido.
- En esa pantalla aparece el enlace **"Cambiar de oficina"**, que te lleva al login global donde puedes indicar otra oficina (o dejar el campo vacío para entrar como super-admin).

### Variables de entorno
| Variable | Descripcion | Default |
|---|---|---|
| `SUPER_ADMIN_EMAIL` | Email del super-admin global | obligatorio |
| `SUPER_ADMIN_PASSWORD` | Contraseña del super-admin | obligatorio |
| `DEFAULT_TENANT_ID` | UUID del tenant inicial | obligatorio |
| `TENANT_BASE_DOMAIN` | Dominio base para subdominios | `gestion.ocasoarmilla.es` |
| `TENANT_RESOLUTION_METHOD` | `subdomain`, `path` o `hybrid` | `subdomain` |
| `SECRET_KEY` | Clave secreta Flask | obligatorio en producción |
| `PORT` | Puerto del servicio | `5050` |
| `DEEPSEEK_API_KEY` | API Key para Asistente IA | - |
| `OCASO_ENV` | Entorno (`production`/`development`) | `production` |
| `DATA_DIR` | Directorio de datos | `/data` |

### Modo desarrollo (con datos de ejemplo)
```bash
OCASO_ENV=development docker compose up -d --build
```
Los datos demo no se generan automáticamente. Usa `python3 seed.py --tenant oficina-inicial` de forma explícita y solo en desarrollo.

### Navegacion

La aplicacion tiene un **menu lateral azul** a la izquierda con todos los modulos. En la parte superior hay un **buscador universal** (busca por nombre, DNI, telefono, poliza, matricula) y un **toggle de modo oscuro** (icono luna). En dispositivos moviles, el menu lateral se oculta y se muestra con el boton flotante azul de la esquina superior izquierda.

---

## 2. Dashboard

**Ruta**: `Dashboard` en el menu lateral

### KPIs del mes en curso
- **Polizas Ocaso este mes**: suma de unidades de polizas Ocaso nuevas (si una poliza multi cuenta como x3, se suma 3)
- **Otras comp. este mes**: polizas nuevas de otras companias
- **Cobrado este mes**: total de primas cobradas en el mes
- **Devuelto**: total de recibos devueltos en el mes

### Selector de mes y año
- El indicador de mes del encabezado (ej. "Agosto 2026") es **clicable** y abre un selector con **Mes** y **Año**.
- Al elegir un periodo se recalculan los KPIs de ese mes y la gráfica de evolucion muestra los 12 meses que terminan en el mes seleccionado.
- Por defecto muestra el mes actual.
- Los paneles **"Primas por ramo"** y **"Clientes con mayor volumen"** reflejan la cartera actual (snapshot), no se filtran por mes.

### Grafico de evolucion
Grafico de los ultimos 12 meses con **barras** (polizas nuevas, eje izquierdo) y **linea** (primas cobradas, eje derecho, formateado en €/k€). La ventana de 12 meses se desplaza con el selector de mes/año.

### Ranking por ramo
Tabla con primas acumuladas por tipo de seguro (Auto, Hogar, Vida, etc.)

### Top 10 clientes
Ranking de los 10 clientes con mayor volumen de prima anual.

---

## 3. Recibos y Cobros

**Ruta**: `Recibos` en el menu lateral

### Tabla principal
- **Filtros**: estado (cobrado/devuelto/pendiente), compania, mes/ano, texto libre
- **Columnas**: cliente, poliza, concepto, importe, fecha emision, fecha cargo, estado (badge de color), gestion

### Colores de estado
- 🟢 **Cobrado**: verde
- 🔴 **Devuelto**: rojo  
- 🟡 **Pendiente**: amarillo

### Gestion de devoluciones
Cada recibo devuelto tiene un boton de engranaje que abre un modal con:
- **Estado de gestion**: contactado, pagado por transferencia, anulado, pendiente de revision
- **Notas**: campo de texto libre

### Cambio rapido de estado
Dropdown en cada fila para marcar directamente como cobrado, devuelto o pendiente.

### Importacion masiva
Boton `Importar` que permite subir archivos CSV o Excel con recibos. Detecta automaticamente las columnas por nombre (cliente, dni, poliza, concepto, importe, fecha, estado). Tambien permite mapeo manual de columnas.

---

## 4. Clientes

**Ruta**: `Clientes` en el menu lateral

### Listado de clientes
Tabla paginada con buscador por nombre, DNI o telefono.

### Ficha de cliente
Al hacer click en un cliente se accede a su ficha con **5 pestanas**:

#### Polizas
Lista de polizas activas del cliente con botones para:
- **Editar** (lapiz): modal con todos los campos de la poliza
- **Dar de baja** (archivo): desactiva la poliza
- **Nueva poliza**: formulario completo de alta

Campos: numero, ramo, capital, prima anual, fecha efecto, fecha vencimiento, IBAN, unidades, detalles.

#### Recibos
Historial de recibos del cliente. Boton `Nuevo Recibo` para dar de alta manualmente.

#### Siniestros
Siniestros asociados. Boton `Nuevo Siniestro` para registrar desde aqui.

#### Historial de contacto
Cronologia de interacciones (llamada, WhatsApp, email, visita) con fecha y notas.

#### Documentos
- **Subir archivo**: seleccionar del disco
- **Camara**: capturar con el dispositivo (se guarda como PDF)
- **Previsualizar, Descargar, Eliminar** cada documento

### Crear cliente
Formulario con: nombre, DNI, direccion, codigo postal (autocompletable con todas las poblaciones de Espana), poblacion, provincia, telefono, email, fecha nacimiento, notas.

### Eliminar cliente
Boton rojo de papelera con confirmacion. Elimina tambien todas sus polizas, recibos y siniestros asociados.

---

## 5. Polizas

**Ruta**: `Polizas` en el menu lateral

Panel independiente para gestionar todas las polizas, sin necesidad de entrar cliente por cliente.

### Filtros
- **Ramo**: desplegable con autocompletado de 37 ramos (Auto, Hogar, Vida, Salud, Comercio, etc.)
- **Estado**: todas, activas, de baja
- **Vencimiento**: proximos 30/60 dias, vencidas
- **Compania**: 40+ aseguradoras (Ocaso, Mapfre, AXA, Allianz...)
- **Buscar**: por cliente, numero de poliza o matricula

### Totales
Contadores de polizas activas, de baja y prima total acumulada.

### Tabla
Columnas ordenables: cliente, poliza, ramo (con indicador x2/x3 si es multi-unidad), compania, prima, capital, fecha efecto, vencimiento, estado.
- Filas en **amarillo**: vencen en <30 dias
- Filas en **rojo**: vencidas

### Acciones
Click en el nombre del cliente lleva a su ficha.

---

## 6. Renovaciones

**Ruta**: `Renovaciones` en el menu lateral

### Contadores superiores
- Vencen en ≤30 dias
- Pendientes de contactar
- Confirmados
- Total proximos 90 dias

### Codigo de colores por urgencia
- 🟢 **Verde**: mas de 60 dias
- 🟡 **Amarillo**: entre 30 y 60 dias
- 🔴 **Rojo**: menos de 30 dias
- ⚫ **Gris**: vencida

### Tabla
Cliente, poliza, ramo, vencimiento, dias restantes, prima, estado de gestion.

### Acciones rapidas
- 📞 **Telefono**: marcar como contactado
- ✉️ **Sobre**: marcar presupuesto enviado
- ✅ **Check**: marcar como confirmado
- Notas opcionales en cada accion

### Estados de gestion
No contactado → Contactado → Presupuesto enviado → Confirmado

### Exportar PDF
Boton que genera un PDF con el listado filtrado para llevar a reuniones.

---

## 7. Listados

**Ruta**: `Listados` en el menu lateral

Informes predefinidos con filtros y totales. Todos tienen boton **Imprimir**.

### Polizas
Filtro por fecha desde/hasta, ramo, estado (activas/bajas) y texto. Totales de cantidad, prima y capital.

### Recibos
Filtro por fecha y estado. Totales separados de cobrado, devuelto y pendiente.

### Produccion
Grafico de evolucion mensual de altas + tabla por ramo con primas y capital. Filtro por ano y mes.

### Siniestros
Filtro por estado (abiertos/cerrados), tipo y texto. Importe estimado total.

Todos los listados se pueden imprimir con el boton de impresora.

---

## 8. Cartera

**Ruta**: `Cartera` en el menu lateral

Control mensual de la cartera activa de la oficina con analisis de IA.

### Subir cartera
- Selecciona **mes** y **año** del informe
- Sube archivo **PDF o Excel** con los datos de la cartera
- Si ya existe un registro para ese mes, se reemplaza

### Grafico de evolucion
Tres lineas de tendencia: polizas activas, asegurados, prima total.

### Analisis IA
- Boton **Analizar** en cada registro
- Boton **Analizar pendientes**: procesa todos los meses sin analizar
- Boton **Reanalizar todo**: fuerza nuevo analisis de todos los meses
- Deepseek extrae datos clave y compara con el mes anterior y año anterior
- Detecta: crecimiento/decrecimiento, polizas perdidas, nuevas incorporaciones, tendencia

### Analisis Anual
- Boton **Analisis anual**: grafico de barras comparando años
- Tabla resumen por año: polizas, asegurados, prima
- IA analiza tendencias interanuales y cambio porcentual

### Informe completo
- Boton **Informe completo**: todos los analisis en una pagina con grafico de evolucion
- **Descargar PDF**: informe corporativo con tabla resumen y analisis por mes

### Historial
Tabla con todos los meses cargados: periodo, archivo, polizas, asegurados, prima y acceso al analisis.

---

## 9. Utilidades

**Ruta**: `Utilidades` en el menu lateral

Herramientas practicas para el dia a dia.

### Comparativa de Polizas
- **Sube 2 o mas PDFs** de polizas de diferentes aseguradoras
- La IA de Deepseek extrae coberturas, capitales, franquicias y primas
- Genera **tabla comparativa** y recomendacion de mejor relacion calidad-precio
- **Descarga el informe en PDF** con formato corporativo Ocaso

---

## 10. Siniestros

**Ruta**: `Siniestros` en el menu lateral

### Tabla principal
- **Columnas**: expediente, cliente, poliza, tipo, fecha ocurrencia, estado, dias sin actualizar
- **Filtros**: por estado y texto
- **Alerta**: filas en rojo si llevan >15 dias sin actualizacion (configurable en Ajustes)

### Estados del siniestro
Abierto → Documentacion enviada → Perito asignado → En taller → En valoracion → Pendiente resolucion → Resuelto → Cerrado

### Ficha del siniestro
- Datos del expediente
- Linea de tiempo con todos los hitos (fecha, estado, notas)
- Documentos asociados con posibilidad de subir nuevos
- Boton `Cambiar estado` para avanzar en el flujo

### Nuevo siniestro
Formulario con: cliente, poliza asociada, numero de expediente, tipo, importe estimado, fechas y descripcion.

---

## 11. Comunicaciones

**Ruta**: `Comunicaciones` en el menu lateral

### Plantillas
Tres tipos de plantillas predefinidas:

#### WhatsApp
Plantillas con variables `{nombre}`, `{poliza}`, `{importe}`, `{fecha}`, `{enlace}`:
- Recibo devuelto
- Renovacion pendiente
- Cita confirmada
- Presupuesto listo
- Siniestro actualizado
- Felicitacion de cumpleanos

#### Email
Plantillas HTML con logo de Ocaso:
- Recibo devuelto
- Renovacion pendiente

#### SMS
Plantillas de texto plano listas para copiar.

### Uso de plantillas
1. Seleccionar plantilla
2. Elegir cliente
3. El mensaje se personaliza automaticamente con los datos del cliente
4. Boton para abrir WhatsApp/Email directamente

### Crear plantillas personalizadas
Boton `Nueva plantilla` para crear tus propias plantillas con las variables disponibles.

---

## 12. WhatsApp

**Ruta**: `WhatsApp` en el menu lateral

### Lista de clientes
Grid de tarjetas con todos los clientes que tienen telefono registrado.

### Filtros
- **Todos**: solo clientes con telefono
- **Con alertas**: clientes con recibos devueltos
- **Contactados/No contactados**: segun historial

### Acciones por cliente
- **Chatear** (boton verde): abre WhatsApp Web con mensaje predefinido
- **Plantillas** (icono documento): elige plantilla o escribe mensaje personalizado
- **Copiar telefono**: copia al portapapeles

### Historial
Registro de todos los mensajes de WhatsApp enviados, con fecha, cliente y contenido.

### Numero de empresa
Se configura en **Ajustes > WhatsApp empresa** (con prefijo 34).

---

## 13. Leads

**Ruta**: `Leads` en el menu lateral

Gestion de prospectos comerciales.

### Estados
- **Nuevo**: recien registrado
- **Contactado**: se ha establecido contacto
- **Presupuesto enviado**: se ha enviado propuesta
- **Ganado**: convertido a cliente
- **Perdido**: no se cerro la venta

### Origenes
Web, Telefono, Presencial, Recomendacion, Otro

### Funcionalidades
- **Grid de tarjetas** con codigo de colores por estado
- **Nuevo lead**: formulario rapido con datos basicos
- **Editar**: todos los campos modificables en modal
- **Cambiar estado**: dropdown con cambio rapido
- **Convertir a cliente** (boton verde): crea automaticamente un cliente con los datos del lead y redirige a la pagina de edicion para completar datos faltantes
- **Eliminar**

---

## 14. Agenda

**Ruta**: `Agenda` en el menu lateral

Agenda personal por usuario. Cada usuario ve solo sus propias entradas.

### Vista Lista
- Entradas del dia seleccionado
- Navegacion por fechas (flechas + selector de fecha)
- Checkbox para marcar como completado
- Tipos: Nota, Llamada, Reunion, Tarea

### Vista Calendario
- Grid mensual con entradas visibles
- Codigo de colores por tipo
- Click en un dia para ver sus entradas

### Funcionalidades
- **Nueva entrada**: modal con titulo, tipo, fecha y notas
- **Toggle completado**: checkbox en cada entrada
- **Eliminar**: con confirmacion

---

## 15. Asistente IA

**Ruta**: `Asistente IA` en el menu lateral

Asistente con IA basado en Deepseek. Dos pestañas:

### Chat
- Conversacion directa con el modelo Deepseek
- El asistente puede consultar los documentos subidos y los datos de la plataforma
- Ejemplos de uso:
  - *"¿Que coberturas tiene el seguro de hogar?"* → consulta documentacion
  - *"¿Que polizas tiene Antonio Garcia?"* → consulta la BD
  - *"¿Cuantos siniestros hay abiertos?"* → consulta estadisticas

### Documentacion
- **Subir documentos**: PDF, Markdown o TXT (max 10MB, multiples archivos)
- **Tabla**: lista de documentos con fecha y tipo
- **Eliminar**: borra el documento del sistema

### Configuracion
Requiere API Key de Deepseek. Se configura en **Ajustes > APIs y servicios**.

---

## 16. Portal de Clientes

**URL**: `/portal`

Portal independiente para que los clientes consulten sus polizas, siniestros y documentos sin acceder al panel de administracion.

### Acceso
- Login con **DNI + contraseña** (independiente de las credenciales de admin)
- Diseño responsive, paleta azul corporativa

### Dashboard del cliente
- **Bienvenida** con el nombre del cliente
- **Tres tarjetas**: polizas activas, siniestros abiertos, documentos
- **Datos de contacto**: DNI, telefono, email, direccion

### Polizas
- Listado de todas las polizas con estado (activa/de baja)
- **Expandible**: click en "Ver detalles" muestra capital, prima, fechas, IBAN, datos del vehiculo

### Siniestros
- Tarjetas por siniestro con **codigo de colores**:
  - 🔴 Rojo: abierto, documentacion enviada, perito, en taller
  - 🟠 Naranja: en valoracion, pendiente resolucion
  - 🟢 Verde: resuelto
  - ⚫ Gris: cerrado
- Expandible: descripcion e importe estimado

### Documentos
- Lista de documentos del cliente con fecha y tipo
- Boton de **descarga** para cada documento

### Activar acceso (administrador)
Desde la **ficha del cliente** en el panel admin:
1. **Toggle switch** en la seccion "Portal de Clientes" para activar el acceso
2. **Boton "Enviar contraseña al email"**: genera contraseña temporal y la envia por correo
3. **Boton "Resetear contraseña"**: genera nueva contraseña (si no tiene email)
4. La contraseña es **temporal**: el cliente debe cambiarla en su primer acceso

### Seguridad
- Sesion independiente del admin (timeout 30 min)
- Contraseñas hasheadas con pbkdf2:sha256
- Cambio forzado de contraseña en primer acceso

---

## 17. Ajustes

**Ruta**: `Ajustes` en el menu lateral

Panel de configuracion unificado.

### Datos de la oficina
Nombre, direccion, telefono, email, WhatsApp empresa.

### Alertas
Dias sin actualizacion para marcar siniestros en rojo (default: 15).

### APIs y servicios
- **Deepseek API Key**: para el Asistente IA. Se puede configurar por variable de entorno o desde esta interfaz.
- **Estadisticas del asistente**: documentos, fragmentos y mensajes.

### Servidor SMTP
Configuracion para envio de correos:
- Servidor SMTP, puerto (default 587), usuario, contraseña
- Remitente (direccion "From")
- **Boton "Enviar test"**: manda un correo de prueba para verificar que la configuracion funciona

### API Keys
Gestion de tokens de acceso para la API externa. Generar claves con nombre (ej: "Zapier", "PowerBI") y revocarlas cuando sea necesario.

### Copia de seguridad y reset
- **Exportar backup**: descarga la base de datos SQLite completa
- **Importar backup**: restaura desde un archivo .db (hace copia de seguridad previa)
- **Borrar todos los datos**: requiere codigo de seguridad y confirmacion. Elimina clientes, polizas, recibos, siniestros... pero conserva los usuarios.

---

## 18. Usuarios y Permisos

**Ruta**: `Usuarios` en el menu lateral (solo visible para administradores)

### Tipos de usuario
- **Administrador**: acceso total a todos los modulos
- **Usuario**: permisos granulares por modulo

### Permisos por modulo
Cada uno de los 13 modulos puede tener:
- **Lectura y Escritura (rw)**: acceso completo
- **Solo Lectura (r)**: puede ver pero no modificar
- **Sin acceso (none)**: el modulo no aparece en el menu

### Gestion de usuarios
- **Crear**: usuario, contrasena, nombre, email, tipo (admin/usuario) y permisos
- **Checkbox "Enviar credenciales por email"**: al crear un usuario, envia sus datos de acceso al correo configurado
- **Editar**: cambiar nombre, email, permisos, activo/inactivo
- **Cambiar contrasena**: desde la pantalla de edicion
- **Eliminar**: borra el usuario (no se puede auto-eliminar)

### Mi Perfil (autogestion)
Cada usuario puede gestionar sus propios datos desde el icono 👤 en la parte inferior del sidebar:
- Cambiar **nombre**
- Cambiar **email** (con verificacion por codigo de 6 digitos enviado al nuevo correo)
- Cambiar **contraseña**
- Activar/desactivar **2FA**

### Visibilidad del menu
El menu lateral se adapta a los permisos de cada usuario. Los modulos sin acceso no aparecen.

---

## 19. Seguridad (2FA)

### Autenticacion en dos pasos
Cada usuario puede activar 2FA con aplicaciones authenticator (Google Authenticator, Authy, Microsoft Authenticator).

### Activar 2FA
1. Ir a **Usuarios > icono del escudo** junto al usuario
2. Escanear el codigo QR con la app
3. Introducir el codigo de 6 digitos para verificar

### Inicio de sesion con 2FA
1. Usuario + contrasena
2. Si 2FA activado → pantalla de codigo de verificacion
3. Introducir codigo de la app authenticator

### Recordar equipo
Checkbox "Recordar este equipo 7 dias" (marcado por defecto). Al verificarte, no se vuelve a pedir el codigo en ese navegador durante 7 dias. Al cerrar sesion se elimina la cookie.

### Recuperacion
- Si un usuario pierde el acceso a su app authenticator, el **propio usuario** puede desactivar 2FA desde **Mi Perfil** > Desactivar 2FA
- El administrador tambien puede desactivarlo desde Usuarios

### Recuperar contrasena
En la pantalla de login, link **"¿Olvidaste tu contrasena?"**:
1. **Por email**: introduces tu email registrado, recibes un codigo de 6 digitos (valido 15 min), introduces el codigo y pones nueva contraseña
2. **Clave de recuperación**: usa el valor seguro configurado en `RECOVERY_MASTER_KEY`; no existe una clave predeterminada.

---

## 20. API Externa

La aplicacion expone una API REST para integraciones con terceros (agentes IA, Zapier, PowerBI, etc.).

> **Documentacion completa**: consulta [API.md](API.md) para la referencia detallada de todos los endpoints, parametros y ejemplos de codigo.

### Resumen de endpoints

| Metodo | Ruta | Descripcion |
|---|---|---|
| GET | `/v1/health` | Estado del servicio |
| GET | `/v1/search?q=` | Busqueda unificada |
| GET | `/v1/stats` | Estadisticas generales |
| GET | `/v1/me` | Info del token |
| GET/POST | `/v1/clientes` | CRUD clientes |
| GET/PUT/DELETE | `/v1/clientes/:id` | Ver/Editar/Eliminar |
| GET/POST | `/v1/clientes/:id/documentos` | Docs de cliente |
| GET/POST | `/v1/polizas` | CRUD polizas |
| GET/PUT/DELETE | `/v1/polizas/:id` | Ver/Editar/Eliminar |
| GET/POST | `/v1/recibos` | CRUD recibos |
| GET | `/v1/siniestros` | Listar siniestros |
| GET/POST | `/v1/leads` | CRUD leads |

### Autenticacion

Header HTTP: `X-API-Key: tu-token`. Los tokens se generan en **Ajustes > API Keys**.

### Ejemplo rapido

```bash
curl -H "X-API-Key: TOKEN" http://localhost:5050/v1/clientes
```

---

## 21. Copias de Seguridad

### Exportar
En **Ajustes > Copia de seguridad y reset > Exportar backup** se descarga un archivo `.db` con toda la base de datos.

### Importar
En **Ajustes > Copia de seguridad y reset > Importar backup** se restaura desde un archivo `.db`. Automaticamente se guarda una copia de la BD actual antes de sobrescribir.

### Reset completo
En **Ajustes > Copia de seguridad y reset > Borrar todos los datos**:
1. Requiere codigo de seguridad
2. Requiere escribir "BORRAR TODO" para confirmar
3. Elimina todos los datos de negocio pero conserva los usuarios y sus permisos

### Volumen Docker
La base de datos persiste en el volumen `ocaso_data`. Al reconstruir el contenedor sin eliminar el volumen (`docker compose down` sin `-v`), los datos se mantienen.

---

## Atajos de teclado

| Tecla | Accion |
|---|---|
| `Ctrl+K` o `/` | Foco en el buscador universal |
| `Esc` | Cerrar sidebar (movil) / cerrar modales |
| `Enter` | Enviar mensaje en chat IA |
| `Shift+Enter` | Nueva linea en chat IA |

---

## Soporte

- **Repositorio**: https://github.com/amolinagrx/agente-ocaso-multitenant
- **Version**: 2.0.0
- **Stack**: Python 3.11 + Flask + SQLite + Bootstrap 5 + HTMX

---

## Resumen de modulos

| Modulo | Icono | Funcion principal |
|---|---|---|
| Dashboard | 🏠 | KPIs, selector de mes/año y graficos |
| Recibos | 🧾 | Gestion de cobros y devoluciones |
| Clientes | 👥 | Fichas, polizas, documentos, portal |
| Polizas | 📄 | Panel de todas las polizas |
| Renovaciones | 📅 | Agenda de vencimientos |
| Listados | 📊 | Informes imprimibles |
| Cartera | 📈 | Control mensual con IA |
| Utilidades | 🔧 | Comparativa de polizas |
| Siniestros | ⚠️ | Seguimiento de expedientes |
| Comunicaciones | 💬 | Plantillas WhatsApp/Email/SMS |
| WhatsApp | 💚 | Envio directo a clientes |
| Leads | 👤 | Prospectos comerciales |
| Agenda | 📝 | Notas y tareas personales |
| Asistente IA | 🤖 | Chat con IA + documentacion |
| Portal Clientes | 🚪 | Acceso clientes a polizas/docs |
| Ajustes | ⚙️ | Configuracion, SMTP, Drive, API Keys |
| Usuarios | 👥🔧 | Gestion de accesos, permisos, 2FA |
