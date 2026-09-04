from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session
from flask_login import login_required
from models import db, Cliente, Poliza, Recibo, Siniestro, HitoSiniestro, HistorialContacto, DocumentoCliente
from datetime import datetime, date
from werkzeug.security import generate_password_hash
import secrets
import os
import io

clientes_bp = Blueprint('clientes', __name__)


@clientes_bp.route('/')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    buscar = request.args.get('buscar', '')

    query = Cliente.query
    if buscar:
        query = query.filter(
            db.or_(
                Cliente.nombre.ilike(f'%{buscar}%'),
                Cliente.dni.ilike(f'%{buscar}%'),
                Cliente.telefono.ilike(f'%{buscar}%'),
                Cliente.email.ilike(f'%{buscar}%')
            )
        )

    pagination = query.order_by(Cliente.nombre).paginate(page=page, per_page=per_page, error_out=False)
    return render_template('clientes/index.html',
                           clientes=pagination.items,
                           pagination=pagination,
                           buscar=buscar)


@clientes_bp.route('/ocr-dni', methods=['POST'])
@login_required
def ocr_dni():
    """OCR para DNI/NIE arrastrado. Devuelve JSON con datos extraídos."""
    file = request.files.get('documento') or request.files.get('file')
    if not file or not file.filename:
        return jsonify({'error': 'Ningún archivo'}), 400
    filename = file.filename.lower()
    if not filename.endswith(('.pdf', '.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.tif')):
        return jsonify({'error': 'Formato no soportado (usa PDF o imagen)'}), 400

    # Guardar temporal y extraer texto
    import tempfile, os, re
    from pathlib import Path
    suffix = Path(filename).suffix or '.pdf'
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    text = ""
    try:
        if filename.endswith('.pdf'):
            try:
                from pypdf import PdfReader
                reader = PdfReader(tmp_path)
                for page in reader.pages:
                    t = page.extract_text() or ""
                    text += t + "\n"
            except Exception:
                text = ""
            # Si PDF no tiene texto (escaneado), renderizar a imagen y OCR
            if not text.strip():
                try:
                    from pdf2image import convert_from_path
                    from PIL import Image
                    import pytesseract
                    # Renderizar primera página a imagen (300 DPI)
                    images = convert_from_path(tmp_path, dpi=300, first_page=1, last_page=1)
                    if images:
                        im = images[0]
                        if im.mode in ('RGBA', 'P'):
                            im = im.convert('RGB')
                        try:
                            text = pytesseract.image_to_string(im, lang='spa+eng')
                        except Exception:
                            text = pytesseract.image_to_string(im)
                except ImportError:
                    # pdf2image no disponible, dejar texto vacío para fallback
                    pass
                except Exception as e:
                    # No bloquear, dejar que regex falle y se use AI fallback
                    print(f"PDF OCR error: {e}")
                    pass
        else:
            try:
                import pytesseract
                from PIL import Image
                im = Image.open(tmp_path)
                # Preprocesar para DNI: escala grises
                if im.mode in ('RGBA', 'P'):
                    im = im.convert('RGB')
                # OCR con español
                try:
                    text = pytesseract.image_to_string(im, lang='spa+eng')
                except Exception:
                    text = pytesseract.image_to_string(im)
            except ImportError:
                return jsonify({'error': 'OCR no disponible en el servidor (falta Tesseract)'}), 500
            except Exception as e:
                return jsonify({'error': f'Error OCR: {e}'}), 500
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    # Parsear DNI español (formato DNIe)
    data = {}
    upper = text.upper()

    # DNI: 8 dígitos + letra, NIE: X/Y/Z + 7 dígitos + letra
    m = re.search(r'\b(\d{8}[A-Z]|[XYZ]\d{7}[A-Z])\b', upper)
    if m:
        data['dni'] = m.group(1)

    # Nombre y apellidos: buscar tras etiquetas APELLIDOS / NOMBRE
    # DNIe layout: "APELLIDOS\nGARCIA LOPEZ\nNOMBRE\nJUAN"
    for label, key in [('APELLIDOS', 'apellidos'), ('NOMBRE', 'nombre')]:
        # Buscar label y capturar siguiente línea con letras
        pat = rf'{label}\s*[:\-]?\s*\n\s*([A-ZÁÉÍÓÚÑ\s\-]+)'
        mm = re.search(pat, upper)
        if mm:
            val = mm.group(1).strip().title()
            # Limpiar: solo letras y espacios, 2-40 chars
            val = re.sub(r'[^A-Za-zÁÉÍÓÚÑáéíóúñ\s\-]', '', val).strip()
            if 2 < len(val) < 50:
                data[key] = val
    # Combinar apellidos + nombre para campo nombre completo
    if 'apellidos' in data or 'nombre' in data:
        full = f"{data.pop('apellidos', '')} {data.get('nombre', '')}".strip()
        if full:
            data['nombre'] = re.sub(r'\s+', ' ', full).strip()
    else:
        # Fallback: buscar 2-3 palabras en mayúsculas que parezcan nombre
        # Evitar palabras comunes del DNI como "ESPAÑA", "DNI", "NACIMIENTO"
        candidates = re.findall(r'\b([A-ZÁÉÍÓÚÑ]{2,}(?:\s+[A-ZÁÉÍÓÚÑ]{2,}){1,3})\b', upper)
        blacklist = {'ESPAÑA', 'DOCUMENTO', 'NACIONAL', 'IDENTIDAD', 'APELLIDOS', 'NOMBRE', 'SEXO', 'NACIMIENTO', 'DOMICILIO', 'LUGAR', 'NACIMIENTO', 'PROVINCIA', 'LOCALIDAD'}
        for cand in candidates:
            words = cand.split()
            if len(words) >= 2 and not any(w in blacklist for w in words):
                # Probable nombre
                data['nombre'] = cand.title()
                break

    # Fecha nacimiento: DD/MM/YYYY o DD-MM-YYYY o YYYY-MM-DD
    if 'fecha_nacimiento' not in data:
        for pat in (r'\b(\d{2})[\/\-](\d{2})[\/\-](\d{4})\b', r'\b(\d{4})[\/\-](\d{2})[\/\-](\d{2})\b'):
            mm = re.search(pat, text)
            if mm:
                try:
                    if len(mm.group(1)) == 4:  # YYYY-MM-DD
                        y, m2, d = mm.group(1), mm.group(2), mm.group(3)
                    else:
                        d, m2, y = mm.group(1), mm.group(2), mm.group(3)
                    # Validar fecha razonable (1900-2010 para nacimiento)
                    if 1900 <= int(y) <= 2010 and 1 <= int(m2) <= 12 and 1 <= int(d) <= 31:
                        data['fecha_nacimiento'] = f"{y}-{m2.zfill(2)}-{d.zfill(2)}"
                        break
                except Exception:
                    pass

    # Domicilio: buscar tras DOMICILIO
    if 'direccion' not in data:
        for label in ('DOMICILIO', 'DIRECCION'):
            pat = rf'{label}\s*[:\-]?\s*\n?\s*([^\n]+)'
            mm = re.search(pat, upper)
            if mm:
                val = mm.group(1).strip()
                # Limpiar prefijos como "C/", "AVDA"
                val = re.sub(r'^(C\/|AVDA\.?|CALLE)\s*', '', val, flags=re.IGNORECASE).strip()
                if len(val) > 5:
                    data['direccion'] = val.title()[:200]
                    break
        if 'direccion' not in data:
            m2 = re.search(r'(C\/[^\n]{5,80}|AVDA[^\n]{5,80}|CALLE[^\n]{5,80})', text, re.IGNORECASE)
            if m2:
                data['direccion'] = m2.group(1).strip()[:200].title()

    # Código postal: 5 dígitos, a menudo cerca de LOCALIDAD/PROVINCIA
    if 'codigo_postal' not in data:
        # Buscar CP cerca de "C.P." ostandalone
        m3 = re.search(r'\b(\d{5})\b', text)
        if m3:
            cp = m3.group(1)
            # Validar CP español (01-52)
            if cp.startswith(('01','02','03','04','05','06','07','08','09','10','11','12','13','14','15','16','17','18','19','20','21','22','23','24','25','26','27','28','29','30','31','32','33','34','35','36','37','38','39','40','41','42','43','44','45','46','47','48','49','50','51','52')):
                data['codigo_postal'] = cp

    # Población y provincia: buscar tras LOCALIDAD/PROVINCIA o usar CP
    if 'poblacion' not in data or 'provincia' not in data:
        for label, key in [('LOCALIDAD', 'poblacion'), ('PROVINCIA', 'provincia'), ('LUGAR DE NACIMIENTO', 'poblacion')]:
            pat = rf'{label}\s*[:\-]?\s*\n?\s*([A-ZÁÉÍÓÚÑ\s\-]+)'
            mm = re.search(pat, upper)
            if mm and key not in data:
                val = mm.group(1).strip().title()
                val = re.sub(r'[^A-Za-zÁÉÍÓÚÑáéíóúñ\s\-]', '', val).strip()
                if 2 < len(val) < 40:
                    data[key] = val

    # Intentar mejorar con AI si está configurado (sobrescribe si AI da más campos)
    try:
        from utils.ai import _get_api_key
        if _get_api_key():
            from utils.ai import chat_with_context
            prompt = (
                "Eres un experto en DNI español. Extrae del siguiente texto OCR de un DNI los campos JSON: "
                "nombre_completo, dni, direccion, codigo_postal, poblacion, provincia, fecha_nacimiento (YYYY-MM-DD). "
                "El DNI tiene formato APELLIDOS, NOMBRE, DOMICILIO, etc. "
                f"Texto OCR:\n{text[:3000]}\n\n"
                "Responde SOLO JSON válido sin explicaciones, ejemplo: {\"nombre_completo\": \"Juan Garcia Lopez\", \"dni\": \"12345678Z\", ...}"
            )
            resp = chat_with_context([{'role': 'user', 'content': prompt}], None, '', '')
            import json as js
            import re as re2
            jm = re2.search(r'\{[^{}]*\{[^{}]*\}[^{}]*\}|\{[^{}]*\}', resp, re.DOTALL)
            if not jm:
                jm = re2.search(r'\{.*\}', resp, re.DOTALL)
            if jm:
                parsed = js.loads(jm.group(0))
                for k in ('nombre_completo', 'dni', 'direccion', 'codigo_postal', 'poblacion', 'provincia', 'fecha_nacimiento'):
                    if parsed.get(k) and str(parsed[k]).strip() and str(parsed[k]).lower() not in ('null', 'none', ''):
                        data[k if k != 'nombre_completo' else 'nombre'] = str(parsed[k]).strip()
    except Exception:
        pass

    # Normalizar nombre a Title Case
    if 'nombre' in data:
        data['nombre'] = ' '.join(w.capitalize() for w in data['nombre'].split())

    return jsonify({'text': text[:3000], 'data': data, 'raw_upper': upper[:500]})


@clientes_bp.route('/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo():
    if request.method == 'POST':
        cliente = Cliente(
            nombre=request.form.get('nombre'),
            dni=request.form.get('dni'),
            direccion=request.form.get('direccion'),
            codigo_postal=request.form.get('codigo_postal'),
            poblacion=request.form.get('poblacion'),
            provincia=request.form.get('provincia'),
            telefono=request.form.get('telefono'),
            email=request.form.get('email'),
            fecha_nacimiento=_parse_date(request.form.get('fecha_nacimiento')),
            notas=request.form.get('notas')
        )
        db.session.add(cliente)
        db.session.commit()

        # Si se arrastró un DNI, guardarlo también en documentación
        dni_file = request.files.get('dni_file')
        if dni_file and dni_file.filename:
            try:
                from services.storage import tenant_upload_path
                from models import DocumentoCliente
                from datetime import datetime as dt
                filename = f"dni_{cliente.id}_{dt.utcnow().strftime('%Y%m%d%H%M%S%f')}_{dni_file.filename}"
                ruta = tenant_upload_path(filename, 'clientes')
                dni_file.save(ruta)
                # Drive si está configurado
                drive_id = None
                try:
                    from utils.drive import is_drive_configured, upload_to_drive
                    if is_drive_configured():
                        drive_id = upload_to_drive(ruta, filename)
                except Exception:
                    pass
                doc = DocumentoCliente(
                    cliente_id=cliente.id,
                    nombre=filename,
                    tipo='dni',
                    ruta=ruta,
                    drive_id=drive_id
                )
                db.session.add(doc)
                db.session.commit()
            except Exception:
                pass

        flash('Cliente creado correctamente', 'success')
        return redirect(url_for('clientes.ficha', id=cliente.id))
    return render_template('clientes/nuevo.html')


@clientes_bp.route('/<int:id>')
@login_required
def ficha(id):
    cliente = Cliente.query.get_or_404(id)
    polizas = cliente.polizas_activas
    recibos = cliente.recibos.filter(Recibo.deleted_at == None).order_by(Recibo.fecha_emision.desc()).limit(50).all()
    siniestros = cliente.siniestros.order_by(Siniestro.fecha_apertura.desc()).all()
    contactos = cliente.contactos.limit(30).all()
    documentos = DocumentoCliente.query.filter_by(cliente_id=cliente.id).order_by(DocumentoCliente.uploaded_at.desc()).all()
    # Deleted items for papelera
    polizas_deleted = Poliza.query.filter_by(cliente_id=cliente.id).filter(Poliza.deleted_at != None).all()
    recibos_deleted = Recibo.query.filter_by(cliente_id=cliente.id).filter(Recibo.deleted_at != None).all()
    portal_password = session.pop(f'portal_password_{id}', None)
    return render_template('clientes/ficha.html',
                           cliente=cliente,
                           polizas=polizas,
                           recibos=recibos,
                           siniestros=siniestros,
                           contactos=contactos,
                           documentos=documentos,
                           portal_password=portal_password,
                           polizas_deleted=polizas_deleted,
                           recibos_deleted=recibos_deleted)


@clientes_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar(id):
    cliente = Cliente.query.get_or_404(id)
    if request.method == 'POST':
        cliente.nombre = request.form.get('nombre')
        cliente.dni = request.form.get('dni')
        cliente.direccion = request.form.get('direccion')
        cliente.codigo_postal = request.form.get('codigo_postal')
        cliente.poblacion = request.form.get('poblacion')
        cliente.provincia = request.form.get('provincia')
        cliente.telefono = request.form.get('telefono')
        cliente.email = request.form.get('email')
        fecha_nac = _parse_date(request.form.get('fecha_nacimiento'))
        cliente.fecha_nacimiento = fecha_nac
        cliente.notas = request.form.get('notas')
        db.session.commit()
        flash('Cliente actualizado', 'success')
        return redirect(url_for('clientes.ficha', id=id))
    return render_template('clientes/editar.html', cliente=cliente)


@clientes_bp.route('/<int:id>/poliza/nueva', methods=['GET', 'POST'])
@login_required
def nueva_poliza(id):
    cliente = Cliente.query.get_or_404(id)
    if request.method == 'POST':
        poliza = Poliza(
            cliente_id=id,
            numero_poliza=request.form.get('numero_poliza'),
            ramo=request.form.get('ramo'),
            compania=request.form.get('compania', 'Ocaso'),
            descripcion=request.form.get('descripcion'),
            capital_asegurado=float(request.form.get('capital_asegurado', 0)),
            prima_anual=float(request.form.get('prima_anual', 0)),
            fecha_efecto=_parse_date(request.form.get('fecha_efecto')),
            fecha_vencimiento=_parse_date(request.form.get('fecha_vencimiento')),
            marca=request.form.get('marca'),
            modelo=request.form.get('modelo'),
            anio=request.form.get('anio', type=int),
            matricula=request.form.get('matricula'),
            tipo_cobertura=request.form.get('tipo_cobertura'),
            tipo_vivienda=request.form.get('tipo_vivienda'),
            metros=request.form.get('metros', type=int),
            continente=float(request.form.get('continente', 0) or 0),
            contenido=float(request.form.get('contenido', 0) or 0),
            numero_cuenta=request.form.get('numero_cuenta', ''),
            unidades=request.form.get('unidades', 1, type=float) or 1.0,
            detalles=request.form.get('detalles', ''),
            frecuencia_pago=request.form.get('frecuencia_pago', 'anual')
        )
        db.session.add(poliza)
        db.session.flush()

        # Auto-generate receipts based on payment frequency
        _generar_recibos_automaticos(poliza)

        db.session.commit()
        flash('Poliza creada correctamente con sus recibos', 'success')
        return redirect(url_for('clientes.ficha', id=id))
    return render_template('clientes/poliza_nueva.html', cliente=cliente)


@clientes_bp.route('/<int:id>/contacto', methods=['POST'])
@login_required
def agregar_contacto(id):
    cliente = Cliente.query.get_or_404(id)
    contacto = HistorialContacto(
        cliente_id=id,
        tipo=request.form.get('tipo'),
        notas=request.form.get('notas'),
        fecha=datetime.utcnow()
    )
    db.session.add(contacto)
    db.session.commit()
    flash('Contacto registrado', 'success')
    return redirect(url_for('clientes.ficha', id=id))


@clientes_bp.route('/<int:id>/subir-documento', methods=['POST'])
@login_required
def subir_documento(id):
    cliente = Cliente.query.get_or_404(id)
    file = request.files.get('documento')
    if file:
        from services.storage import tenant_upload_path
        filename = f"cliente_{id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{file.filename}"
        ruta = tenant_upload_path(filename, 'clientes')
        file.save(ruta)

        # Convert to PDF if it's an image from camera
        if file.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.bmp')):
            try:
                from PIL import Image
                img = Image.open(ruta)
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                pdf_name = filename.rsplit('.', 1)[0] + '.pdf'
                pdf_ruta = tenant_upload_path(pdf_name, 'clientes')
                img.save(pdf_ruta, 'PDF', optimize=True, resolution=150)
                os.remove(ruta)
                ruta = pdf_ruta
                filename = pdf_name
            except ImportError:
                pass

        # Upload to Google Drive si está configurado (credenciales en BD)
        drive_id = None
        try:
            from utils.drive import is_drive_configured, upload_to_drive
            if is_drive_configured():
                drive_id = upload_to_drive(ruta, filename)
        except Exception:
            pass

        doc = DocumentoCliente(
            cliente_id=id,
            nombre=filename,
            tipo=request.form.get('tipo', 'otro'),
            ruta=ruta,
            drive_id=drive_id
        )
        db.session.add(doc)
        db.session.commit()
        flash('Documento subido', 'success')
    return redirect(url_for('clientes.ficha', id=id, _anchor='documentos'))


@clientes_bp.route('/<int:id>/documento/<int:doc_id>/eliminar', methods=['POST'])
@login_required
def eliminar_documento(id, doc_id):
    from services.storage import validated_tenant_file
    doc = DocumentoCliente.query.get_or_404(doc_id)
    if doc.drive_id:
        from utils.drive import delete_from_drive
        delete_from_drive(doc.drive_id)
    if doc.ruta:
        try:
            os.remove(validated_tenant_file(doc.ruta))
        except FileNotFoundError:
            pass
    db.session.delete(doc)
    db.session.commit()
    flash('Documento eliminado', 'success')
    return redirect(url_for('clientes.ficha', id=id, _anchor='documentos'))


@clientes_bp.route('/<int:id>/documento/<int:doc_id>/descargar')
@login_required
def descargar_documento(id, doc_id):
    from flask import send_file
    from services.storage import validated_tenant_file
    doc = DocumentoCliente.query.get_or_404(doc_id)
    if doc.drive_id:
        from utils.drive import download_from_drive
        data = download_from_drive(doc.drive_id)
        if data:
            return send_file(io.BytesIO(data), download_name=doc.nombre, as_attachment=True)
    return send_file(validated_tenant_file(doc.ruta), download_name=doc.nombre, as_attachment=True)


@clientes_bp.route('/<int:id>/documento/<int:doc_id>/preview')
@login_required
def preview_documento(id, doc_id):
    from flask import send_file
    from services.storage import validated_tenant_file
    doc = DocumentoCliente.query.get_or_404(doc_id)
    if doc.drive_id:
        from utils.drive import download_from_drive
        data = download_from_drive(doc.drive_id)
        if data:
            return send_file(io.BytesIO(data), download_name=doc.nombre)
    return send_file(validated_tenant_file(doc.ruta))


@clientes_bp.route('/<int:id>/poliza/<int:poliza_id>/editar', methods=['POST'])
@login_required
def editar_poliza(id, poliza_id):
    poliza = Poliza.query.get_or_404(poliza_id)
    poliza.numero_poliza = request.form.get('numero_poliza', poliza.numero_poliza)
    poliza.ramo = request.form.get('ramo', poliza.ramo)
    poliza.compania = request.form.get('compania', poliza.compania)
    poliza.descripcion = request.form.get('descripcion', poliza.descripcion)
    poliza.capital_asegurado = float(request.form.get('capital_asegurado', poliza.capital_asegurado or 0))
    poliza.prima_anual = float(request.form.get('prima_anual', poliza.prima_anual or 0))
    poliza.fecha_efecto = _parse_date(request.form.get('fecha_efecto')) or poliza.fecha_efecto
    poliza.fecha_vencimiento = _parse_date(request.form.get('fecha_vencimiento')) or poliza.fecha_vencimiento
    poliza.numero_cuenta = request.form.get('numero_cuenta', poliza.numero_cuenta)
    poliza.unidades = request.form.get('unidades', 1, type=float) or 1.0
    poliza.detalles = request.form.get('detalles', poliza.detalles)
    poliza.frecuencia_pago = request.form.get('frecuencia_pago', poliza.frecuencia_pago)
    poliza.activa = request.form.get('activa', 'true') == 'true'

    if poliza.ramo == 'auto':
        poliza.marca = request.form.get('marca', poliza.marca)
        poliza.modelo = request.form.get('modelo', poliza.modelo)
        poliza.anio = request.form.get('anio', type=int) or poliza.anio
        poliza.matricula = request.form.get('matricula', poliza.matricula)
        poliza.tipo_cobertura = request.form.get('tipo_cobertura', poliza.tipo_cobertura)
    elif poliza.ramo == 'hogar':
        poliza.tipo_vivienda = request.form.get('tipo_vivienda', poliza.tipo_vivienda)
        poliza.metros = request.form.get('metros', type=int) or poliza.metros
        poliza.continente = float(request.form.get('continente', 0) or 0)
        poliza.contenido = float(request.form.get('contenido', 0) or 0)

    db.session.commit()
    flash('Poliza actualizada', 'success')
    return redirect(url_for('clientes.ficha', id=id))


@clientes_bp.route('/<int:id>/poliza/<int:poliza_id>/baja', methods=['POST'])
@login_required
def dar_baja_poliza(id, poliza_id):
    poliza = Poliza.query.get_or_404(poliza_id)
    poliza.activa = False
    poliza.fecha_baja = date.today()
    poliza.deleted_at = datetime.utcnow()
    # Soft-delete pending receipts
    Recibo.query.filter_by(poliza_id=poliza_id, estado='pendiente').update(
        {'deleted_at': datetime.utcnow()}, synchronize_session=False)
    db.session.commit()
    flash(f'Poliza {poliza.numero_poliza} dada de baja. Recibos pendientes movidos a papelera.', 'warning')
    return redirect(url_for('clientes.ficha', id=id))


@clientes_bp.route('/<int:id>/recibo/nuevo', methods=['POST'])
@login_required
def nuevo_recibo(id):
    cliente = Cliente.query.get_or_404(id)
    recibo = Recibo(
        cliente_id=id,
        poliza_id=request.form.get('poliza_id', type=int) or None,
        numero_poliza=request.form.get('numero_poliza', ''),
        concepto=request.form.get('concepto', ''),
        importe=float(request.form.get('importe', 0)),
        fecha_emision=_parse_date(request.form.get('fecha_emision')) or date.today(),
        fecha_cargo=_parse_date(request.form.get('fecha_cargo')) or date.today(),
        estado=request.form.get('estado', 'pendiente'),
        compania=request.form.get('compania', 'Ocaso'),
        notas=request.form.get('notas', '')
    )
    db.session.add(recibo)
    db.session.commit()
    flash(f'Recibo de {recibo.importe:.2f}€ creado', 'success')
    return redirect(url_for('clientes.ficha', id=id))


@clientes_bp.route('/<int:id>/siniestro/nuevo', methods=['POST'])
@login_required
def nuevo_siniestro(id):
    cliente = Cliente.query.get_or_404(id)
    siniestro = Siniestro(
        cliente_id=id,
        poliza_id=request.form.get('poliza_id', type=int) or None,
        numero_expediente=request.form.get('numero_expediente', ''),
        tipo=request.form.get('tipo', ''),
        descripcion=request.form.get('descripcion', ''),
        fecha_ocurrencia=_parse_date(request.form.get('fecha_ocurrencia')) or date.today(),
        fecha_apertura=_parse_date(request.form.get('fecha_apertura')) or date.today(),
        estado='abierto',
        fecha_ultima_actualizacion=datetime.utcnow(),
        importe_estimado=float(request.form.get('importe_estimado', 0) or 0)
    )
    db.session.add(siniestro)
    db.session.flush()

    hito = HitoSiniestro(
        siniestro_id=siniestro.id,
        fecha=datetime.utcnow(),
        estado='abierto',
        notas=request.form.get('notas_iniciales', 'Apertura de siniestro desde ficha de cliente')
    )
    db.session.add(hito)
    db.session.commit()
    flash('Siniestro registrado correctamente', 'success')
    return redirect(url_for('clientes.ficha', id=id))


@clientes_bp.route('/<int:id>/polizas-json')
@login_required
def polizas_json(id):
    polizas = Poliza.query.filter_by(cliente_id=id).order_by(Poliza.activa.desc()).all()
    return jsonify([{
        'id': p.id,
        'numero_poliza': p.numero_poliza,
        'ramo': p.ramo,
        'prima_anual': p.prima_anual,
        'activa': p.activa
    } for p in polizas])


@clientes_bp.route('/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar(id):
    cliente = Cliente.query.get_or_404(id)
    nombre = cliente.nombre
    db.session.delete(cliente)
    db.session.commit()
    flash(f'Cliente {nombre} eliminado correctamente', 'success')
    return redirect(url_for('clientes.index'))


@clientes_bp.route('/<int:id>/activar_portal', methods=['POST'])
@login_required
def activar_portal(id):
    cliente = Cliente.query.get_or_404(id)
    password = secrets.token_urlsafe(6)[:8]
    cliente.portal_password = generate_password_hash(password, method='pbkdf2:sha256')
    cliente.portal_activo = True
    cliente.portal_password_temporal = True
    db.session.commit()

    if cliente.email:
        try:
            from utils.email import send_email
            html = f'''
            <div style="font-family:Arial;max-width:600px;margin:0 auto;border:1px solid #ddd;border-radius:8px;overflow:hidden">
                <div style="background:#003396;color:white;padding:20px;text-align:center"><h2>Ocaso Seguros - Armilla</h2></div>
                <div style="padding:20px">
                    <h3>Acceso al portal de clientes</h3>
                    <p>Hola <strong>{cliente.nombre}</strong>, ya puedes acceder al portal.</p>
                    <p><strong>DNI:</strong> {cliente.dni}</p>
                    <p><strong>Contrasena:</strong> <code>{password}</code></p>
                    <p><a href="http://gestion.ocasoarmilla.es/portal">Acceder al portal</a></p>
                </div>
            </div>'''
            ok = send_email(cliente.email, 'Acceso al portal de clientes - Ocaso', html)
            if ok:
                flash(f'Portal activado. Contrasena enviada a {cliente.email}', 'success')
            else:
                flash(f'Portal activado. Contrasena guardada (SMTP no configurado)', 'warning')
            session[f'portal_password_{id}'] = password
            return redirect(url_for('clientes.ficha', id=id))
        except Exception:
            session[f'portal_password_{id}'] = password
            flash(f'Portal activado.', 'warning')
            return redirect(url_for('clientes.ficha', id=id))
    else:
        session[f'portal_password_{id}'] = password
        flash(f'Portal activado.', 'warning')
        return redirect(url_for('clientes.ficha', id=id))


@clientes_bp.route('/<int:id>/desactivar_portal', methods=['POST'])
@login_required
def desactivar_portal(id):
    cliente = Cliente.query.get_or_404(id)
    cliente.portal_activo = False
    cliente.portal_password = None
    cliente.portal_token = None
    db.session.commit()
    flash('Acceso al portal desactivado', 'success')
    return redirect(url_for('clientes.ficha', id=id))


@clientes_bp.route('/<int:id>/reenviar_password', methods=['POST'])
@login_required
def reenviar_password(id):
    cliente = Cliente.query.get_or_404(id)
    if not cliente.portal_activo:
        flash('El portal no esta activo para este cliente', 'warning')
        return redirect(url_for('clientes.ficha', id=id))

    password = secrets.token_urlsafe(6)[:8]
    cliente.portal_password = generate_password_hash(password, method='pbkdf2:sha256')
    cliente.portal_password_temporal = True
    db.session.commit()

    if cliente.email:
        try:
            from utils.email import send_email
            html = f'''
            <div style="font-family:Arial;max-width:600px;margin:0 auto;border:1px solid #ddd;border-radius:8px;overflow:hidden">
                <div style="background:#003396;color:white;padding:20px;text-align:center"><h2>Ocaso Seguros</h2></div>
                <div style="padding:20px"><p>Hola <strong>{cliente.nombre}</strong>, tu nueva contrasena:</p>
                <h2 style="text-align:center">{password}</h2></div>
            </div>'''
            ok = send_email(cliente.email, 'Nueva contrasena - Portal Ocaso', html)
            if ok:
                flash(f'Nueva contrasena enviada a {cliente.email}', 'success')
            else:
                flash(f'Contrasena guardada (SMTP no configurado)', 'warning')
            session[f'portal_password_{id}'] = password
            return redirect(url_for('clientes.ficha', id=id))
        except Exception:
            session[f'portal_password_{id}'] = password
            return redirect(url_for('clientes.ficha', id=id))
    else:
        session[f'portal_password_{id}'] = password
        flash(f'Nueva contrasena generada.', 'warning')

    return redirect(url_for('clientes.ficha', id=id))


def _generar_recibos_automaticos(poliza):
    """Auto-generate receipts for a year based on payment frequency."""
    from dateutil.relativedelta import relativedelta
    frecuencias = {
        'anual': 1,
        'semestral': 2,
        'trimestral': 4,
        'bimestral': 6,
        'mensual': 12,
        '0/30/60': 3,
    }
    num_recibos = frecuencias.get(poliza.frecuencia_pago or 'anual', 1)
    if not poliza.fecha_efecto:
        return

    importe = round(poliza.prima_anual / num_recibos, 2)
    fecha_base = poliza.fecha_efecto

    for i in range(num_recibos):
        if poliza.frecuencia_pago == '0/30/60':
            meses_offset = i
        elif poliza.frecuencia_pago == 'anual':
            meses_offset = 0
        else:
            meses_offset = i * (12 // num_recibos)

        fecha_emision = fecha_base + relativedelta(months=meses_offset)
        fecha_cargo = fecha_emision + relativedelta(days=5)

        recibo = Recibo(
            cliente_id=poliza.cliente_id,
            poliza_id=poliza.id,
            numero_poliza=poliza.numero_poliza,
            concepto=f'Prima {poliza.ramo.title()} - {fecha_emision.strftime("%b %Y")} ({i+1}/{num_recibos})',
            importe=importe,
            fecha_emision=fecha_emision,
            fecha_cargo=fecha_cargo,
            estado='pendiente',
            compania=poliza.compania,
        )
        db.session.add(recibo)


def _parse_date(val):
    """Parse a date string to a Python date object."""
    if not val or (isinstance(val, str) and not val.strip()):
        return None
    if isinstance(val, date):
        return val
    try:
        from datetime import datetime as dt
        return dt.strptime(str(val), '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None
