-- Fresh multi-tenant SQLite schema. Existing databases must use scripts/migrate_to_multitenant.py.
PRAGMA foreign_keys=ON;
BEGIN;
CREATE TABLE tenants (
	id VARCHAR(36) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	subdomain VARCHAR(100) NOT NULL, 
	config_json TEXT NOT NULL, 
	created_at DATETIME NOT NULL, 
	active BOOLEAN NOT NULL, 
	PRIMARY KEY (id)
);
CREATE INDEX ix_tenants_active ON tenants (active);
CREATE UNIQUE INDEX ix_tenants_subdomain ON tenants (subdomain);
CREATE TABLE cartera_altas (
	id INTEGER NOT NULL, 
	mes_desde INTEGER, 
	anio_desde INTEGER, 
	mes_hasta INTEGER, 
	anio_hasta INTEGER, 
	poliza_base VARCHAR(20), 
	certificado VARCHAR(20), 
	producto VARCHAR(200), 
	tipo_recibo VARCHAR(100), 
	prima_neta FLOAT, 
	tenant_id VARCHAR(36) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);
CREATE INDEX ix_cartera_altas_tenant_id_id ON cartera_altas (tenant_id, id);
CREATE TABLE cartera_bajas (
	id INTEGER NOT NULL, 
	mes_desde INTEGER, 
	anio_desde INTEGER, 
	mes_hasta INTEGER, 
	anio_hasta INTEGER, 
	poliza_base VARCHAR(20), 
	certificado VARCHAR(20), 
	producto VARCHAR(200), 
	tipo_recibo VARCHAR(100), 
	prima_neta FLOAT, 
	renumerada BOOLEAN, 
	poliza_renumerada_a VARCHAR(20), 
	tenant_id VARCHAR(36) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);
CREATE INDEX ix_cartera_bajas_tenant_id_id ON cartera_bajas (tenant_id, id);
CREATE TABLE clientes (
	id INTEGER NOT NULL, 
	nombre VARCHAR(200) NOT NULL, 
	dni VARCHAR(20), 
	direccion VARCHAR(300), 
	codigo_postal VARCHAR(10), 
	poblacion VARCHAR(100), 
	provincia VARCHAR(100), 
	telefono VARCHAR(30), 
	email VARCHAR(120), 
	fecha_nacimiento DATE, 
	fecha_alta DATETIME, 
	notas TEXT, 
	alerta_devoluciones BOOLEAN, 
	portal_activo BOOLEAN, 
	portal_password VARCHAR(256), 
	portal_token VARCHAR(100), 
	portal_password_temporal BOOLEAN, 
	tenant_id VARCHAR(36) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_clientes_tenant_dni UNIQUE (tenant_id, dni), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);
CREATE INDEX ix_clientes_tenant_id_id ON clientes (tenant_id, id);
CREATE INDEX ix_clientes_tenant_nombre ON clientes (tenant_id, nombre);
CREATE TABLE configuracion (
	id INTEGER NOT NULL, 
	clave VARCHAR(100) NOT NULL, 
	valor VARCHAR(500), 
	tenant_id VARCHAR(36) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_configuracion_tenant_clave UNIQUE (tenant_id, clave), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);
CREATE INDEX ix_configuracion_tenant_id_id ON configuracion (tenant_id, id);
CREATE TABLE documentos_conocimiento (
	id INTEGER NOT NULL, 
	nombre VARCHAR(300) NOT NULL, 
	tipo VARCHAR(10), 
	contenido_raw TEXT, 
	num_chunks INTEGER, 
	created_at DATETIME, 
	tenant_id VARCHAR(36) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);
CREATE INDEX ix_documentos_conocimiento_tenant_id_id ON documentos_conocimiento (tenant_id, id);
CREATE TABLE mensajes_asistente (
	id INTEGER NOT NULL, 
	rol VARCHAR(20) NOT NULL, 
	contenido TEXT NOT NULL, 
	contexto_usado TEXT, 
	created_at DATETIME, 
	tenant_id VARCHAR(36) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);
CREATE INDEX ix_mensajes_asistente_tenant_id_id ON mensajes_asistente (tenant_id, id);
CREATE TABLE plantillas_comunicacion (
	id INTEGER NOT NULL, 
	nombre VARCHAR(100) NOT NULL, 
	tipo VARCHAR(30), 
	asunto VARCHAR(200), 
	contenido TEXT NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);
CREATE INDEX ix_plantillas_comunicacion_tenant_id_id ON plantillas_comunicacion (tenant_id, id);
CREATE TABLE users (
	id INTEGER NOT NULL, 
	tenant_id VARCHAR(36), 
	username VARCHAR(80) NOT NULL, 
	password VARCHAR(200) NOT NULL, 
	nombre VARCHAR(200), 
	is_admin BOOLEAN, 
	activo BOOLEAN, 
	permisos TEXT, 
	totp_secret VARCHAR(64), 
	totp_enabled BOOLEAN, 
	password_temporal BOOLEAN, 
	email VARCHAR(120), 
	email_verified BOOLEAN, 
	email_verification_code VARCHAR(10), 
	recovery_code VARCHAR(64), 
	recovery_code_expires DATETIME, 
	is_super_admin BOOLEAN DEFAULT 0 NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_users_tenant_username UNIQUE (tenant_id, username), 
	CONSTRAINT uq_users_tenant_email UNIQUE (tenant_id, email), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);
CREATE INDEX ix_users_tenant_id_id ON users (tenant_id, id);
CREATE UNIQUE INDEX uq_users_global_email ON users (email) WHERE tenant_id IS NULL;
CREATE TABLE agenda (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	fecha DATE NOT NULL, 
	titulo VARCHAR(300) NOT NULL, 
	notas TEXT, 
	tipo VARCHAR(30), 
	completado BOOLEAN, 
	created_at DATETIME, 
	tenant_id VARCHAR(36) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);
CREATE INDEX ix_agenda_tenant_id_id ON agenda (tenant_id, id);
CREATE TABLE api_keys (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	nombre VARCHAR(100) NOT NULL, 
	token VARCHAR(64) NOT NULL, 
	activo BOOLEAN, 
	created_at DATETIME, 
	last_used DATETIME, 
	tenant_id VARCHAR(36) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	UNIQUE (token), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);
CREATE INDEX ix_api_keys_tenant_id_id ON api_keys (tenant_id, id);
CREATE TABLE cartera (
	id INTEGER NOT NULL, 
	mes INTEGER NOT NULL, 
	anio INTEGER NOT NULL, 
	nombre_archivo VARCHAR(300), 
	ruta_archivo VARCHAR(500), 
	contenido_texto TEXT, 
	num_polizas INTEGER, 
	num_asegurados INTEGER, 
	prima_total FLOAT, 
	analisis_ia TEXT, 
	user_id INTEGER, 
	created_at DATETIME, 
	tenant_id VARCHAR(36) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);
CREATE INDEX ix_cartera_tenant_id_id ON cartera (tenant_id, id);
CREATE TABLE cartera_ficheros (
	id INTEGER NOT NULL, 
	mes INTEGER NOT NULL, 
	anio INTEGER NOT NULL, 
	nombre_fichero VARCHAR(300), 
	ruta VARCHAR(500), 
	hash_md5 VARCHAR(64), 
	num_filas INTEGER, 
	num_polizas INTEGER, 
	prima_neta_total FLOAT, 
	fecha_subida DATETIME, 
	user_id INTEGER, 
	tenant_id VARCHAR(36) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_cartera_tenant_mes_anio UNIQUE (tenant_id, mes, anio), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);
CREATE INDEX ix_cartera_ficheros_tenant_id_id ON cartera_ficheros (tenant_id, id);
CREATE TABLE chunks_conocimiento (
	id INTEGER NOT NULL, 
	documento_id INTEGER NOT NULL, 
	texto TEXT NOT NULL, 
	embedding TEXT, 
	indice INTEGER, 
	created_at DATETIME, 
	tenant_id VARCHAR(36) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(documento_id) REFERENCES documentos_conocimiento (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);
CREATE INDEX ix_chunks_conocimiento_tenant_id_id ON chunks_conocimiento (tenant_id, id);
CREATE TABLE comunicaciones (
	id INTEGER NOT NULL, 
	cliente_id INTEGER NOT NULL, 
	fecha DATETIME, 
	tipo VARCHAR(30), 
	plantilla VARCHAR(100), 
	contenido TEXT, 
	enviado BOOLEAN, 
	tenant_id VARCHAR(36) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(cliente_id) REFERENCES clientes (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);
CREATE INDEX ix_comunicaciones_tenant_id_id ON comunicaciones (tenant_id, id);
CREATE TABLE documentos_cliente (
	id INTEGER NOT NULL, 
	cliente_id INTEGER NOT NULL, 
	nombre VARCHAR(300), 
	tipo VARCHAR(50), 
	ruta VARCHAR(500), 
	drive_id VARCHAR(200), 
	uploaded_at DATETIME, 
	tenant_id VARCHAR(36) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(cliente_id) REFERENCES clientes (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);
CREATE INDEX ix_documentos_cliente_tenant_id_id ON documentos_cliente (tenant_id, id);
CREATE TABLE historial_contacto (
	id INTEGER NOT NULL, 
	cliente_id INTEGER NOT NULL, 
	fecha DATETIME, 
	tipo VARCHAR(30), 
	notas TEXT, 
	tenant_id VARCHAR(36) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(cliente_id) REFERENCES clientes (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);
CREATE INDEX ix_historial_contacto_tenant_id_id ON historial_contacto (tenant_id, id);
CREATE TABLE leads (
	id INTEGER NOT NULL, 
	nombre VARCHAR(200) NOT NULL, 
	telefono VARCHAR(30), 
	email VARCHAR(120), 
	dni VARCHAR(20), 
	direccion VARCHAR(300), 
	codigo_postal VARCHAR(10), 
	poblacion VARCHAR(100), 
	provincia VARCHAR(100), 
	ramo_interes VARCHAR(100), 
	origen VARCHAR(50), 
	estado VARCHAR(30), 
	notas TEXT, 
	cliente_id INTEGER, 
	user_id INTEGER, 
	created_at DATETIME, 
	updated_at DATETIME, 
	tenant_id VARCHAR(36) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(cliente_id) REFERENCES clientes (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);
CREATE INDEX ix_leads_tenant_id_id ON leads (tenant_id, id);
CREATE TABLE polizas (
	id INTEGER NOT NULL, 
	cliente_id INTEGER NOT NULL, 
	numero_poliza VARCHAR(50) NOT NULL, 
	ramo VARCHAR(50) NOT NULL, 
	compania VARCHAR(50), 
	descripcion VARCHAR(300), 
	capital_asegurado FLOAT, 
	prima_anual FLOAT, 
	fecha_efecto DATE NOT NULL, 
	fecha_vencimiento DATE NOT NULL, 
	activa BOOLEAN, 
	fecha_baja DATE, 
	numero_cuenta VARCHAR(34), 
	unidades FLOAT, 
	detalles TEXT, 
	frecuencia_pago VARCHAR(20), 
	deleted_at DATETIME, 
	marca VARCHAR(50), 
	modelo VARCHAR(50), 
	anio INTEGER, 
	matricula VARCHAR(20), 
	tipo_cobertura VARCHAR(50), 
	tipo_vivienda VARCHAR(50), 
	metros INTEGER, 
	continente FLOAT, 
	contenido FLOAT, 
	tenant_id VARCHAR(36) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_polizas_tenant_numero UNIQUE (tenant_id, numero_poliza), 
	FOREIGN KEY(cliente_id) REFERENCES clientes (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);
CREATE INDEX ix_polizas_tenant_cliente ON polizas (tenant_id, cliente_id);
CREATE INDEX ix_polizas_tenant_id_id ON polizas (tenant_id, id);
CREATE TABLE cartera_polizas (
	id INTEGER NOT NULL, 
	fichero_id INTEGER NOT NULL, 
	poliza_base VARCHAR(20), 
	certificado VARCHAR(20), 
	producto VARCHAR(200), 
	tipo_recibo VARCHAR(100), 
	prima_neta FLOAT, 
	prima_comisionable FLOAT, 
	produccion FLOAT, 
	conservacion FLOAT, 
	pol_corr FLOAT, 
	aseg VARCHAR(50), 
	tenant_id VARCHAR(36) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(fichero_id) REFERENCES cartera_ficheros (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);
CREATE INDEX ix_cartera_polizas_tenant_id_id ON cartera_polizas (tenant_id, id);
CREATE TABLE recibos (
	id INTEGER NOT NULL, 
	cliente_id INTEGER NOT NULL, 
	poliza_id INTEGER, 
	numero_poliza VARCHAR(50), 
	concepto VARCHAR(200), 
	importe FLOAT NOT NULL, 
	fecha_emision DATE, 
	fecha_cargo DATE, 
	estado VARCHAR(20), 
	estado_gestion VARCHAR(30), 
	notas TEXT, 
	compania VARCHAR(50), 
	created_at DATETIME, 
	deleted_at DATETIME, 
	tenant_id VARCHAR(36) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(cliente_id) REFERENCES clientes (id), 
	FOREIGN KEY(poliza_id) REFERENCES polizas (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);
CREATE INDEX ix_recibos_tenant_estado ON recibos (tenant_id, estado);
CREATE INDEX ix_recibos_tenant_id_id ON recibos (tenant_id, id);
CREATE TABLE renovaciones (
	id INTEGER NOT NULL, 
	poliza_id INTEGER NOT NULL, 
	cliente_id INTEGER NOT NULL, 
	fecha_vencimiento DATE NOT NULL, 
	prima FLOAT, 
	estado VARCHAR(30), 
	notas TEXT, 
	created_at DATETIME, 
	tenant_id VARCHAR(36) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(poliza_id) REFERENCES polizas (id), 
	FOREIGN KEY(cliente_id) REFERENCES clientes (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);
CREATE INDEX ix_renovaciones_tenant_id_id ON renovaciones (tenant_id, id);
CREATE TABLE siniestros (
	id INTEGER NOT NULL, 
	cliente_id INTEGER NOT NULL, 
	poliza_id INTEGER, 
	numero_expediente VARCHAR(50) NOT NULL, 
	tipo VARCHAR(50) NOT NULL, 
	descripcion TEXT, 
	fecha_ocurrencia DATE, 
	fecha_apertura DATE, 
	estado VARCHAR(30), 
	fecha_ultima_actualizacion DATETIME, 
	importe_estimado FLOAT, 
	tenant_id VARCHAR(36) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_siniestros_tenant_expediente UNIQUE (tenant_id, numero_expediente), 
	FOREIGN KEY(cliente_id) REFERENCES clientes (id), 
	FOREIGN KEY(poliza_id) REFERENCES polizas (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);
CREATE INDEX ix_siniestros_tenant_id_id ON siniestros (tenant_id, id);
CREATE TABLE documentos_siniestro (
	id INTEGER NOT NULL, 
	siniestro_id INTEGER NOT NULL, 
	nombre VARCHAR(300), 
	tipo VARCHAR(50), 
	ruta VARCHAR(500), 
	drive_id VARCHAR(200), 
	uploaded_at DATETIME, 
	tenant_id VARCHAR(36) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(siniestro_id) REFERENCES siniestros (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);
CREATE INDEX ix_documentos_siniestro_tenant_id_id ON documentos_siniestro (tenant_id, id);
CREATE TABLE hitos_siniestro (
	id INTEGER NOT NULL, 
	siniestro_id INTEGER NOT NULL, 
	fecha DATETIME, 
	estado VARCHAR(30), 
	notas TEXT, 
	tenant_id VARCHAR(36) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(siniestro_id) REFERENCES siniestros (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);
CREATE INDEX ix_hitos_siniestro_tenant_id_id ON hitos_siniestro (tenant_id, id);
COMMIT;
