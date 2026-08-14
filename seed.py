#!/usr/bin/env python3
"""
Seed script: generates realistic demo data for Ocaso Gestion.
"""

import random
from datetime import date, datetime, timedelta
from models import db, Cliente, Poliza, Recibo, Renovacion, Siniestro, HitoSiniestro, DocumentoSiniestro, Configuracion, HistorialContacto, DocumentoCliente, COMPANIAS_ESPANA, RAMOS_ESPANA

NOMBRES = [
    "Antonio Garcia Lopez", "Maria Rodriguez Sanchez", "Jose Martinez Fernandez",
    "Carmen Gonzalez Perez", "Francisco Lopez Garcia", "Ana Sanchez Rodriguez",
    "Juan Perez Martinez", "Isabel Fernandez Gonzalez", "Manuel Ruiz Diaz",
    "Dolores Moreno Jimenez", "Javier Hernandez Ruiz", "Concepcion Alonso Torres",
    "Miguel Angel Jimenez Castro", "Rosa Maria Navarro Ortega", "Carlos Serrano Romero",
    "Pilar Gutierrez Molina", "Andres Ramirez Delgado", "Laura Castillo Rivas",
    "David Vazquez Blanco", "Marta Dominguez Bravo", "Alejandro Ibanez Gil",
    "Sara Morales Prieto", "Daniel Herrero Marin", "Beatriz Fuentes Guerrero",
    "Rafael Ortega Flores", "Elena Cortes Mendoza", "Pedro Sanz Pena",
    "Cristina Medina Esteban", "Ignacio Rubio Nunez", "Lucia Guerrero Soto",
    "Pablo Molina Benitez", "Paula Santos Caballero", "Sergio Leon Santana",
    "Teresa Pardo Hidalgo", "Alberto Cabrera Aguilar", "Noelia Vega Reyes",
    "Roberto Roman Campos", "Silvia Bosch Tellez", "Luis Angel Ferrer Gallego",
    "Patricia Aguilar Cano", "Oscar Soler Moya", "Veronica Lozano Bravo",
    "Fernando Iglesias Ajenjo", "Clara Gallego Cuesta", "Jorge Montes Arenas",
    "Sandra Bueno Pascual", "Adrian Rivas Parra", "Marina Cruz Exposito",
    "Hector Pena Iglesias", "Ines Redondo Vicente"
]

DNIS = [
    "12345678A", "23456789B", "34567890C", "45678901D", "56789012E",
    "67890123F", "78901234G", "89012345H", "90123456I", "11223344J",
    "22334455K", "33445566L", "44556677M", "55667788N", "66778899P",
    "77889900Q", "88990011R", "99001122S", "10111213T", "12131415U",
    "14151617V", "15161718W", "16171819X", "17181920Y", "18202122Z",
    "19222324A", "20232425B", "21232426C", "22242627D", "23252628E",
    "24252729F", "25262830G", "26272831H", "27282932I", "28293033J",
    "29303134K", "30313235L", "31323336M", "32333437N", "33343538P",
    "34353639Q", "35363740R", "36373841S", "37383942T", "38394043U",
    "39404144V", "40414245W", "41424346X", "42434447Y", "43444548Z"
]

DIRECCIONES = [
    "C/ Real 15, Armilla", "Avda. de la Libertad 42, Armilla",
    "C/ Granada 8, Armilla", "Plaza Mayor 3, Armilla",
    "C/ San Miguel 21, Armilla", "Avda. de Andalucia 55, Armilla",
    "C/ Nueva 7, Armilla", "C/ del Sol 12, Armilla",
    "Paseo de la Estacion 33, Armilla", "C/ Jardines 18, Armilla"
]

TELEFONOS = [
    "958123456", "958234567", "958345678", "958456789", "958567890",
    "958678901", "958789012", "958890123", "958901234", "958012345",
    "610123456", "620234567", "630345678", "640456789", "650567890",
    "660678901", "670789012", "680890123", "690901234", "699012345"
]

MARCAS_AUTO = ["Toyota", "Seat", "Renault", "Peugeot", "Volkswagen", "Opel", "Citroen", "Ford", "Hyundai", "Kia"]
MODELOS_AUTO = ["C3", "Ibiza", "Leon", "Corsa", "Golf", "Focus", "308", "Clio", "Tucson", "Rio"]

RAMOS = RAMOS_ESPANA  # usa la lista completa de modelos.py
ESTADOS_RECIBO = ["cobrado", "cobrado", "cobrado", "cobrado", "cobrado", "devuelto", "pendiente"]
TIPOS_SINIESTRO = [
    "accidente_trafico", "robo", "incendio", "danos_agua",
    "responsabilidad_civil", "cristales", "fallecimiento", "otro"
]
ESTADOS_SINIESTRO = [
    "abierto", "documentacion_enviada", "perito_asignado",
    "en_taller", "en_valoracion", "pendiente_resolucion",
    "resuelto", "cerrado"
]


def run_seed():
    print("Borrando datos existentes...")
    from models import Comunicacion, MensajeAsistente
    Comunicacion.query.delete()
    MensajeAsistente.query.delete()
    Siniestro.query.delete()
    Renovacion.query.delete()
    Recibo.query.delete()
    Poliza.query.delete()
    HistorialContacto.query.delete()
    DocumentoCliente.query.delete()
    Cliente.query.delete()
    Configuracion.query.delete()
    db.session.commit()

    # Config
    db.session.add(Configuracion(clave='oficina_nombre', valor='Ocaso Armilla'))
    db.session.add(Configuracion(clave='oficina_direccion', valor='C/ Real 12, 18100 Armilla (Granada)'))
    db.session.add(Configuracion(clave='oficina_telefono', valor='958 123 456'))
    db.session.add(Configuracion(clave='oficina_email', valor='armilla@ocaso.es'))

    db.session.commit()
    print("Configuracion creada.")

    clientes = []
    for i in range(50):
        telefono = random.choice(TELEFONOS) if random.random() > 0.1 else None
        c = Cliente(
            nombre=NOMBRES[i],
            dni=DNIS[i],
            direccion=random.choice(DIRECCIONES),
            codigo_postal=str(random.randint(18001, 18200)),
            poblacion='Armilla',
            provincia='Granada',
            telefono=str(telefono) if telefono else None,
            email=f"{NOMBRES[i].split()[0].lower()}{i}@email.com" if random.random() > 0.3 else None,
            fecha_nacimiento=date(random.randint(1960, 2000), random.randint(1, 12), random.randint(1, 28)) if random.random() > 0.2 else None
        )
        db.session.add(c)
        db.session.flush()
        clientes.append(c)

    db.session.commit()
    print(f"{len(clientes)} clientes creados.")

    polizas = []
    for cliente in clientes:
        num_polizas = random.randint(2, 5)
        for j in range(num_polizas):
            ramo = random.choice(RAMOS)
            fecha_efecto = date.today() - timedelta(days=random.randint(30, 720))
            fecha_venc = fecha_efecto + timedelta(days=365 + random.randint(-30, 90))

            prima_base = {
                'auto': random.randint(250, 900),
                'hogar': random.randint(80, 300),
                'vida': random.randint(100, 400),
                'decesos': random.randint(40, 150),
                'accidentes': random.randint(60, 200),
                'comercio': random.randint(200, 800)
            }.get(ramo, 200)

            p = Poliza(
                cliente_id=cliente.id,
                numero_poliza=f"OC-{ramo[:2].upper()}-{100000 + len(polizas):06d}",
                ramo=ramo,
                compania=random.choice(['Ocaso'] * 5 + [c for c in COMPANIAS_ESPANA if c != 'Ocaso']),
                descripcion=f"Seguro de {ramo}" if ramo != 'auto' else f"Vehiculo {random.choice(MARCAS_AUTO)} {random.choice(MODELOS_AUTO)}",
                capital_asegurado=random.randint(10000, 200000),
                prima_anual=prima_base,
                fecha_efecto=fecha_efecto,
                fecha_vencimiento=fecha_venc,
                activa=(fecha_venc > date.today() or random.random() > 0.15),
                numero_cuenta=f"ES{random.randint(10,99)} {random.randint(1000,9999)} {random.randint(1000,9999)} {random.randint(10,99)} {random.randint(1000000000, 9999999999)}" if random.random() > 0.3 else '',
                unidades=random.choice([1, 1, 1, 1, 2, 3]) if random.random() > 0.3 else 1
            )

            if ramo == 'auto':
                p.marca = random.choice(MARCAS_AUTO)
                p.modelo = random.choice(MODELOS_AUTO)
                p.anio = random.randint(2015, 2024)
                p.matricula = f"{random.randint(1000,9999)} {chr(random.randint(66,90))}{chr(random.randint(66,90))}{chr(random.randint(66,90))}"
                p.tipo_cobertura = random.choice(["terceros", "terceros_ampliado", "todo_riesgo"])
            elif ramo == 'hogar':
                p.tipo_vivienda = random.choice(["piso", "adosado", "unifamiliar", "atico"])
                p.metros = random.randint(60, 200)
                p.continente = random.randint(80000, 300000)
                p.contenido = random.randint(15000, 80000)

            db.session.add(p)
            db.session.flush()
            polizas.append(p)

    db.session.commit()
    print(f"{len(polizas)} polizas creadas.")

    recibos_count = 0
    hoy = date.today()
    for poliza in polizas:
        if not poliza.activa:
            continue
        for mes_offset in range(12, 0, -1):
            mes_inicio = hoy.replace(day=1) - timedelta(days=30 * mes_offset)
            mes_inicio = mes_inicio.replace(day=1)
            dia = min(28, random.randint(1, 28))
            fecha_emision = mes_inicio.replace(day=dia)

            estado = random.choice(ESTADOS_RECIBO)
            recibo = Recibo(
                cliente_id=poliza.cliente_id,
                poliza_id=poliza.id,
                numero_poliza=poliza.numero_poliza,
                concepto=f"Prima {poliza.ramo.title()} - {fecha_emision.strftime('%b %Y')}",
                importe=round(poliza.prima_anual / 12 + random.uniform(-5, 10), 2),
                fecha_emision=fecha_emision,
                fecha_cargo=fecha_emision + timedelta(days=5),
                estado=estado,
                compania=poliza.compania,
                estado_gestion='contactado' if estado == 'devuelto' and random.random() > 0.5 else None,
                notas='Devolucion bancaria' if estado == 'devuelto' else None
            )
            db.session.add(recibo)
            recibos_count += 1

    db.session.commit()
    print(f"{recibos_count} recibos creados.")

    for cliente in clientes:
        count = Recibo.query.filter_by(cliente_id=cliente.id, estado='devuelto').count()
        if count >= 2:
            cliente.alerta_devoluciones = True

    db.session.commit()
    print("Alertas de clientes actualizadas.")

    num_siniestros = random.randint(8, 12)
    siniestro_polizas = random.sample(polizas, min(num_siniestros, len(polizas)))
    for i, poliza in enumerate(siniestro_polizas):
        dias_atras = random.randint(5, 300)
        fecha_ocurrencia = date.today() - timedelta(days=dias_atras)
        fecha_apertura = fecha_ocurrencia + timedelta(days=random.randint(1, 5))
        estado = random.choice(ESTADOS_SINIESTRO)

        s = Siniestro(
            cliente_id=poliza.cliente_id,
            poliza_id=poliza.id,
            numero_expediente=f"EXP-2025-{1000 + i:04d}",
            tipo=random.choice(TIPOS_SINIESTRO),
            descripcion=f"Siniestro de {random.choice(TIPOS_SINIESTRO).replace('_',' ')}. "
                        f"Ocurrido el {fecha_ocurrencia.strftime('%d/%m/%Y')}.",
            fecha_ocurrencia=fecha_ocurrencia,
            fecha_apertura=fecha_apertura,
            estado=estado,
            fecha_ultima_actualizacion=datetime.utcnow() - timedelta(days=random.randint(0, 30)),
            importe_estimado=random.randint(500, 15000)
        )
        db.session.add(s)
        db.session.flush()

        hitos_estados = ESTADOS_SINIESTRO[:ESTADOS_SINIESTRO.index(estado)+1]
        for j, h_estado in enumerate(hitos_estados):
            hito = HitoSiniestro(
                siniestro_id=s.id,
                fecha=fecha_apertura + timedelta(days=j * random.randint(3, 15)),
                estado=h_estado,
                notas=f"Transicion a {h_estado.replace('_',' ').title()}" if j > 0 else "Apertura del siniestro"
            )
            db.session.add(hito)

    db.session.commit()
    print(f"{num_siniestros} siniestros creados.")

    renov_count = 0
    limite = date.today() + timedelta(days=90)
    for poliza in polizas:
        if poliza.activa and poliza.fecha_vencimiento and poliza.fecha_vencimiento <= limite:
            renov = Renovacion(
                poliza_id=poliza.id,
                cliente_id=poliza.cliente_id,
                fecha_vencimiento=poliza.fecha_vencimiento,
                prima=poliza.prima_anual,
                estado=random.choice(['no_contactado', 'no_contactado', 'contactado', 'presupuesto_enviado', 'confirmado'])
            )
            db.session.add(renov)
            renov_count += 1

    db.session.commit()
    print(f"{renov_count} renovaciones creadas.")
    print("\n--- Seed completado ---")


if __name__ == '__main__':
    import argparse
    from app import create_app
    from models import Tenant
    from services.tenant_context import tenant_context

    parser = argparse.ArgumentParser(description='Carga datos demo en un tenant existente.')
    parser.add_argument('--tenant', required=True, help='Subdominio del tenant de destino')
    args = parser.parse_args()
    app = create_app()
    with app.app_context():
        tenant = Tenant.query.filter_by(subdomain=args.tenant, active=True).first()
        if tenant is None:
            parser.error('Tenant no encontrado o inactivo.')
        with tenant_context(tenant):
            run_seed()
