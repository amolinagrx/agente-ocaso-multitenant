from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy import event
from sqlalchemy.engine import Engine
import uuid
import sqlite3

db = SQLAlchemy()


@event.listens_for(Engine, 'connect')
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.execute('PRAGMA busy_timeout=5000')
        cursor.close()


def new_uuid():
    """Return a portable UUID string for SQLite and PostgreSQL."""
    return str(uuid.uuid4())


class TenantScopedMixin:
    """Marker shared by every model whose rows belong to one tenant."""

    @declared_attr
    def tenant_id(cls):
        return db.Column(
            db.String(36), db.ForeignKey('tenants.id'), nullable=False
        )

COMPANIAS_ESPANA = [
    'Ocaso',
    'Mapfre',
    'Mutua Madrilena',
    'Allianz',
    'AXA',
    'Generali',
    'Zurich',
    'Santalucia',
    'Catalana Occidente',
    'Pelayo',
    'Reale',
    'Helvetia',
    'FIATC',
    'Linea Directa',
    'Verti',
    'Qualitas Auto',
    'Liberty',
    'Caser',
    'Asisa',
    'Adeslas',
    'Sanitas',
    'DKV',
    'Asemfa',
    'MGS',
    'Prevision Medica',
    'Aegon',
    'MetLife',
    'Vidacaixa',
    'Ibercaja',
    'Unicorp Vida',
    'Asefa',
    'Plus Ultra',
    'Mussap',
    'SegurCaixa',
    'RGA',
    'Bansabadell',
    'Bilbao',
    'Lagun Aro',
    'Previsora General',
    'Premaat',
    'Otra',
]

RAMOS_ESPANA = [
    'Auto',
    'Hogar',
    'Vida',
    'Vida Riesgo',
    'Vida Ahorro',
    'Decesos',
    'Accidentes',
    'Salud',
    'Asistencia Sanitaria',
    'Comercio',
    'Negocio',
    'Responsabilidad Civil',
    'Comunidades',
    'Empresas',
    'PYME',
    'Transportes',
    'Flotas',
    'Embarcaciones',
    'Caza',
    'Pesca',
    'Mascotas',
    'Agricola',
    'Industrial',
    'Construccion',
    'Todo Riesgo Construccion',
    'Credito',
    'Caucion',
    'Defensa Juridica',
    'Asistencia en Viaje',
    'Dependencia',
    'Jubilacion',
    'Planes de Pensiones',
    'Multirriesgo',
    'Aeronaves',
    'Ciberriesgo',
    'Proteccion de Pagos',
    'Baja Laboral',
]


class Tenant(db.Model):
    __tablename__ = 'tenants'
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    name = db.Column(db.String(200), nullable=False)
    subdomain = db.Column(db.String(100), nullable=False, unique=True, index=True)
    config_json = db.Column(db.Text, nullable=False, default='{}')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    active = db.Column(db.Boolean, nullable=False, default=True, index=True)


class User(UserMixin, TenantScopedMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.String(36), db.ForeignKey('tenants.id'), nullable=True)
    username = db.Column(db.String(80), nullable=False)
    password = db.Column(db.String(200), nullable=False)
    nombre = db.Column(db.String(200))
    is_admin = db.Column(db.Boolean, default=False)
    activo = db.Column(db.Boolean, default=True)
    permisos = db.Column(db.Text, default='{}')
    totp_secret = db.Column(db.String(64))
    totp_enabled = db.Column(db.Boolean, default=False)
    password_temporal = db.Column(db.Boolean, default=False)
    email = db.Column(db.String(120))
    email_verified = db.Column(db.Boolean, default=False)
    email_verification_code = db.Column(db.String(10))
    recovery_code = db.Column(db.String(64))
    recovery_code_expires = db.Column(db.DateTime)
    is_super_admin = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'username', name='uq_users_tenant_username'),
        db.UniqueConstraint('tenant_id', 'email', name='uq_users_tenant_email'),
        db.Index(
            'uq_users_global_email', 'email', unique=True,
            sqlite_where=tenant_id.is_(None),
            postgresql_where=tenant_id.is_(None),
        ),
        db.Index('ix_users_tenant_id_id', 'tenant_id', 'id'),
    )

    def set_password(self, raw):
        self.password = generate_password_hash(raw, method='pbkdf2:sha256')

    def check_password(self, raw):
        return check_password_hash(self.password, raw)

    def tiene_permiso(self, modulo, nivel='r'):
        """Verifica si el usuario tiene al menos nivel de permiso en un modulo."""
        if self.is_admin:
            return True
        import json
        try:
            p = json.loads(self.permisos or '{}')
        except json.JSONDecodeError:
            return False
        perm = p.get(modulo, 'none')
        if perm == 'rw':
            return True
        if perm == 'r' and nivel == 'r':
            return True
        return False


class Cliente(TenantScopedMixin, db.Model):
    __tablename__ = 'clientes'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False)
    dni = db.Column(db.String(20))
    direccion = db.Column(db.String(300))
    codigo_postal = db.Column(db.String(10))
    poblacion = db.Column(db.String(100))
    provincia = db.Column(db.String(100))
    telefono = db.Column(db.String(30))
    email = db.Column(db.String(120))
    fecha_nacimiento = db.Column(db.Date)
    fecha_alta = db.Column(db.DateTime, default=datetime.utcnow)
    notas = db.Column(db.Text)
    alerta_devoluciones = db.Column(db.Boolean, default=False)
    portal_activo = db.Column(db.Boolean, default=False)
    portal_password = db.Column(db.String(256))
    portal_token = db.Column(db.String(100))
    portal_password_temporal = db.Column(db.Boolean, default=True)
    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'dni', name='uq_clientes_tenant_dni'),
        db.Index('ix_clientes_tenant_id_id', 'tenant_id', 'id'),
        db.Index('ix_clientes_tenant_nombre', 'tenant_id', 'nombre'),
    )

    polizas = db.relationship('Poliza', backref='cliente', lazy='dynamic', cascade='all, delete-orphan')
    recibos = db.relationship('Recibo', backref='cliente', lazy='dynamic', cascade='all, delete-orphan')
    siniestros = db.relationship('Siniestro', backref='cliente', lazy='dynamic', cascade='all, delete-orphan')
    contactos = db.relationship('HistorialContacto', backref='cliente', lazy='dynamic', cascade='all, delete-orphan',
                                order_by='HistorialContacto.fecha.desc()')
    comunicaciones = db.relationship('Comunicacion', backref='cliente', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def devoluciones_count(self):
        return self.recibos.filter(Recibo.estado == 'devuelto').count()

    @property
    def polizas_activas(self):
        return self.polizas.filter(Poliza.activa == True).all()


class Poliza(TenantScopedMixin, db.Model):
    __tablename__ = 'polizas'
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    numero_poliza = db.Column(db.String(50), nullable=False)
    ramo = db.Column(db.String(50), nullable=False)
    compania = db.Column(db.String(50), default='Ocaso')
    descripcion = db.Column(db.String(300))
    capital_asegurado = db.Column(db.Float, default=0)
    prima_anual = db.Column(db.Float, default=0)
    fecha_efecto = db.Column(db.Date, nullable=False)
    fecha_vencimiento = db.Column(db.Date, nullable=False)
    activa = db.Column(db.Boolean, default=True)
    fecha_baja = db.Column(db.Date)
    numero_cuenta = db.Column(db.String(34))
    unidades = db.Column(db.Float, default=1.0)
    detalles = db.Column(db.Text)
    frecuencia_pago = db.Column(db.String(20), default='anual')
    deleted_at = db.Column(db.DateTime)

    # Vehicle-specific fields
    marca = db.Column(db.String(50))
    modelo = db.Column(db.String(50))
    anio = db.Column(db.Integer)
    matricula = db.Column(db.String(20))
    tipo_cobertura = db.Column(db.String(50))
    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'numero_poliza', name='uq_polizas_tenant_numero'),
        db.Index('ix_polizas_tenant_id_id', 'tenant_id', 'id'),
        db.Index('ix_polizas_tenant_cliente', 'tenant_id', 'cliente_id'),
    )

    # Home-specific fields
    tipo_vivienda = db.Column(db.String(50))
    metros = db.Column(db.Integer)
    continente = db.Column(db.Float)
    contenido = db.Column(db.Float)

    siniestros = db.relationship('Siniestro', backref='poliza', lazy='dynamic',
                                 cascade='all, delete-orphan')
    renovaciones = db.relationship('Renovacion', backref='poliza', lazy='dynamic',
                                   cascade='all, delete-orphan')


class Recibo(TenantScopedMixin, db.Model):
    __tablename__ = 'recibos'
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    poliza_id = db.Column(db.Integer, db.ForeignKey('polizas.id'))
    numero_poliza = db.Column(db.String(50))
    concepto = db.Column(db.String(200))
    importe = db.Column(db.Float, nullable=False)
    fecha_emision = db.Column(db.Date)
    fecha_cargo = db.Column(db.Date)
    estado = db.Column(db.String(20), default='pendiente')  # cobrado, devuelto, pendiente
    estado_gestion = db.Column(db.String(30))  # contactado, transferencia, anulado, pendiente_revision
    notas = db.Column(db.Text)
    compania = db.Column(db.String(50), default='Ocaso')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    deleted_at = db.Column(db.DateTime)
    __table_args__ = (
        db.Index('ix_recibos_tenant_id_id', 'tenant_id', 'id'),
        db.Index('ix_recibos_tenant_estado', 'tenant_id', 'estado'),
    )

    poliza_rel = db.relationship('Poliza', backref='recibos')


class Renovacion(TenantScopedMixin, db.Model):
    __tablename__ = 'renovaciones'
    id = db.Column(db.Integer, primary_key=True)
    poliza_id = db.Column(db.Integer, db.ForeignKey('polizas.id'), nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    fecha_vencimiento = db.Column(db.Date, nullable=False)
    prima = db.Column(db.Float, default=0)
    estado = db.Column(db.String(30), default='no_contactado')
    # no_contactado, contactado, presupuesto_enviado, confirmado
    notas = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Siniestro(TenantScopedMixin, db.Model):
    __tablename__ = 'siniestros'
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    poliza_id = db.Column(db.Integer, db.ForeignKey('polizas.id'))
    numero_expediente = db.Column(db.String(50), nullable=False)
    tipo = db.Column(db.String(50), nullable=False)
    descripcion = db.Column(db.Text)
    fecha_ocurrencia = db.Column(db.Date)
    fecha_apertura = db.Column(db.Date, default=date.today)
    estado = db.Column(db.String(30), default='abierto')
    # abierto, documentacion_enviada, perito_asignado, en_taller,
    # en_valoracion, pendiente_resolucion, resuelto, cerrado
    fecha_ultima_actualizacion = db.Column(db.DateTime, default=datetime.utcnow)
    importe_estimado = db.Column(db.Float, default=0)
    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'numero_expediente', name='uq_siniestros_tenant_expediente'),
        db.Index('ix_siniestros_tenant_id_id', 'tenant_id', 'id'),
    )

    hitos = db.relationship('HitoSiniestro', backref='siniestro', lazy='dynamic',
                            cascade='all, delete-orphan', order_by='HitoSiniestro.fecha.desc()')
    documentos = db.relationship('DocumentoSiniestro', backref='siniestro', lazy='dynamic',
                                 cascade='all, delete-orphan')


class HitoSiniestro(TenantScopedMixin, db.Model):
    __tablename__ = 'hitos_siniestro'
    id = db.Column(db.Integer, primary_key=True)
    siniestro_id = db.Column(db.Integer, db.ForeignKey('siniestros.id'), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    estado = db.Column(db.String(30))
    notas = db.Column(db.Text)


class DocumentoSiniestro(TenantScopedMixin, db.Model):
    __tablename__ = 'documentos_siniestro'
    id = db.Column(db.Integer, primary_key=True)
    siniestro_id = db.Column(db.Integer, db.ForeignKey('siniestros.id'), nullable=False)
    nombre = db.Column(db.String(300))
    tipo = db.Column(db.String(50))  # parte_amistoso, presupuesto, informe_pericial, otro
    ruta = db.Column(db.String(500))
    drive_id = db.Column(db.String(200))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


class HistorialContacto(TenantScopedMixin, db.Model):
    __tablename__ = 'historial_contacto'
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    tipo = db.Column(db.String(30))  # llamada, whatsapp, email, visita
    notas = db.Column(db.Text)


class DocumentoCliente(TenantScopedMixin, db.Model):
    __tablename__ = 'documentos_cliente'
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    nombre = db.Column(db.String(300))
    tipo = db.Column(db.String(50))
    ruta = db.Column(db.String(500))
    drive_id = db.Column(db.String(200))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


class Comunicacion(TenantScopedMixin, db.Model):
    __tablename__ = 'comunicaciones'
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    tipo = db.Column(db.String(30))  # whatsapp, email, sms
    plantilla = db.Column(db.String(100))
    contenido = db.Column(db.Text)
    enviado = db.Column(db.Boolean, default=False)


class PlantillaComunicacion(TenantScopedMixin, db.Model):
    __tablename__ = 'plantillas_comunicacion'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(30))  # whatsapp, email, sms
    asunto = db.Column(db.String(200))
    contenido = db.Column(db.Text, nullable=False)


class Configuracion(TenantScopedMixin, db.Model):
    __tablename__ = 'configuracion'
    id = db.Column(db.Integer, primary_key=True)
    clave = db.Column(db.String(100), nullable=False)
    valor = db.Column(db.String(500))
    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'clave', name='uq_configuracion_tenant_clave'),
        db.Index('ix_configuracion_tenant_id_id', 'tenant_id', 'id'),
    )


class DocumentoConocimiento(TenantScopedMixin, db.Model):
    __tablename__ = 'documentos_conocimiento'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(300), nullable=False)
    tipo = db.Column(db.String(10))
    contenido_raw = db.Column(db.Text)
    num_chunks = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    chunks = db.relationship('ChunkConocimiento', backref='documento', lazy='dynamic',
                             cascade='all, delete-orphan')


class ChunkConocimiento(TenantScopedMixin, db.Model):
    __tablename__ = 'chunks_conocimiento'
    id = db.Column(db.Integer, primary_key=True)
    documento_id = db.Column(db.Integer, db.ForeignKey('documentos_conocimiento.id'), nullable=False)
    texto = db.Column(db.Text, nullable=False)
    embedding = db.Column(db.Text)
    indice = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class MensajeAsistente(TenantScopedMixin, db.Model):
    __tablename__ = 'mensajes_asistente'
    id = db.Column(db.Integer, primary_key=True)
    rol = db.Column(db.String(20), nullable=False)  # user, assistant, system
    contenido = db.Column(db.Text, nullable=False)
    contexto_usado = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Agenda(TenantScopedMixin, db.Model):
    __tablename__ = 'agenda'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    fecha = db.Column(db.Date, nullable=False, default=date.today)
    titulo = db.Column(db.String(300), nullable=False)
    notas = db.Column(db.Text)
    tipo = db.Column(db.String(30), default='nota')  # nota, llamada, reunion, tarea
    completado = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Lead(TenantScopedMixin, db.Model):
    __tablename__ = 'leads'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False)
    telefono = db.Column(db.String(30))
    email = db.Column(db.String(120))
    dni = db.Column(db.String(20))
    direccion = db.Column(db.String(300))
    codigo_postal = db.Column(db.String(10))
    poblacion = db.Column(db.String(100))
    provincia = db.Column(db.String(100))
    ramo_interes = db.Column(db.String(100))
    origen = db.Column(db.String(50), default='web')
    estado = db.Column(db.String(30), default='nuevo')
    notas = db.Column(db.Text)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Cartera(TenantScopedMixin, db.Model):
    __tablename__ = 'cartera'
    id = db.Column(db.Integer, primary_key=True)
    mes = db.Column(db.Integer, nullable=False)
    anio = db.Column(db.Integer, nullable=False)
    nombre_archivo = db.Column(db.String(300))
    ruta_archivo = db.Column(db.String(500))
    contenido_texto = db.Column(db.Text)
    num_polizas = db.Column(db.Integer)
    num_asegurados = db.Column(db.Integer)
    prima_total = db.Column(db.Float)
    analisis_ia = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ApiKey(TenantScopedMixin, db.Model):
    __tablename__ = 'api_keys'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False)
    activo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used = db.Column(db.DateTime)


class CarteraFichero(TenantScopedMixin, db.Model):
    __tablename__ = 'cartera_ficheros'
    id = db.Column(db.Integer, primary_key=True)
    mes = db.Column(db.Integer, nullable=False)
    anio = db.Column(db.Integer, nullable=False)
    nombre_fichero = db.Column(db.String(300))
    ruta = db.Column(db.String(500))
    hash_md5 = db.Column(db.String(64))
    num_filas = db.Column(db.Integer)
    num_polizas = db.Column(db.Integer)
    prima_neta_total = db.Column(db.Float)
    fecha_subida = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'mes', 'anio', name='uq_cartera_tenant_mes_anio'),
        db.Index('ix_cartera_ficheros_tenant_id_id', 'tenant_id', 'id'),
    )

    polizas = db.relationship('CarteraPoliza', backref='fichero', lazy='dynamic', cascade='all, delete-orphan')


class CarteraPoliza(TenantScopedMixin, db.Model):
    __tablename__ = 'cartera_polizas'
    id = db.Column(db.Integer, primary_key=True)
    fichero_id = db.Column(db.Integer, db.ForeignKey('cartera_ficheros.id'), nullable=False)
    poliza_base = db.Column(db.String(20))
    certificado = db.Column(db.String(20))
    producto = db.Column(db.String(200))
    tipo_recibo = db.Column(db.String(100))
    prima_neta = db.Column(db.Float, default=0)
    prima_comisionable = db.Column(db.Float, default=0)
    produccion = db.Column(db.Float, default=0)
    conservacion = db.Column(db.Float, default=0)
    pol_corr = db.Column(db.Float, default=0)
    aseg = db.Column(db.String(50))


class CarteraBaja(TenantScopedMixin, db.Model):
    __tablename__ = 'cartera_bajas'
    id = db.Column(db.Integer, primary_key=True)
    mes_desde = db.Column(db.Integer)
    anio_desde = db.Column(db.Integer)
    mes_hasta = db.Column(db.Integer)
    anio_hasta = db.Column(db.Integer)
    poliza_base = db.Column(db.String(20))
    certificado = db.Column(db.String(20))
    producto = db.Column(db.String(200))
    tipo_recibo = db.Column(db.String(100))
    prima_neta = db.Column(db.Float)
    renumerada = db.Column(db.Boolean, default=False)
    poliza_renumerada_a = db.Column(db.String(20))


class CarteraAlta(TenantScopedMixin, db.Model):
    __tablename__ = 'cartera_altas'
    id = db.Column(db.Integer, primary_key=True)
    mes_desde = db.Column(db.Integer)
    anio_desde = db.Column(db.Integer)
    mes_hasta = db.Column(db.Integer)
    anio_hasta = db.Column(db.Integer)
    poliza_base = db.Column(db.String(20))
    certificado = db.Column(db.String(20))
    producto = db.Column(db.String(200))
    tipo_recibo = db.Column(db.String(100))
    prima_neta = db.Column(db.Float)


# Every tenant-owned table has a compound lookup index. Explicitly declared
# indexes above are retained for the busiest domain-specific access paths.
_TENANT_MODELS = (
    User, Cliente, Poliza, Recibo, Renovacion, Siniestro, HitoSiniestro,
    DocumentoSiniestro, HistorialContacto, DocumentoCliente, Comunicacion,
    PlantillaComunicacion, Configuracion, DocumentoConocimiento,
    ChunkConocimiento, MensajeAsistente, Agenda, Lead, Cartera, ApiKey,
    CarteraFichero, CarteraPoliza, CarteraBaja, CarteraAlta,
)
for _model in _TENANT_MODELS:
    _index_name = f'ix_{_model.__tablename__}_tenant_id_id'
    if not any(index.name == _index_name for index in _model.__table__.indexes):
        db.Index(_index_name, _model.tenant_id, _model.id)
