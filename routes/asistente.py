import os
import json
from flask import Blueprint, render_template, request, jsonify, current_app, redirect, url_for, flash
from flask_login import login_required
from models import db, DocumentoConocimiento, ChunkConocimiento, MensajeAsistente
from utils.ai import (
    extract_text_from_file, chunk_text, generate_embedding,
    search_relevant_chunks, get_platform_context, chat_with_context,
    summarize_document, build_system_prompt
)
from datetime import datetime

asistente_bp = Blueprint('asistente', __name__)


@asistente_bp.route('/')
@login_required
def index():
    documentos = DocumentoConocimiento.query.order_by(
        DocumentoConocimiento.created_at.desc()
    ).all()
    mensajes = MensajeAsistente.query.order_by(
        MensajeAsistente.created_at.asc()
    ).limit(100).all()
    return render_template('asistente/index.html',
                           documentos=documentos,
                           mensajes=mensajes)


@asistente_bp.route('/chat', methods=['POST'])
@login_required
def chat():
    pregunta = request.form.get('mensaje', '').strip()
    if not pregunta:
        return jsonify({'respuesta': '', 'error': 'Mensaje vacio'})

    # Save user message
    user_msg = MensajeAsistente(rol='user', contenido=pregunta)
    db.session.add(user_msg)
    db.session.commit()

    # Search relevant knowledge from documents on disk
    docs = DocumentoConocimiento.query.all()
    knowledge_text = ''
    if docs:
        knowledge_parts = []
        for doc in docs:
            try:
                texto = extract_text_from_file(doc.contenido_raw, doc.nombre)
                if texto and not texto.startswith('ERROR'):
                    knowledge_parts.append(f'--- {doc.nombre} ---\n{texto[:4000]}')
            except Exception:
                pass
        knowledge_text = '\n\n'.join(knowledge_parts) if knowledge_parts else ''
        relevant = None  # No chunk-based search, use full docs

    # Get platform context
    platform_ctx = get_platform_context(pregunta)

    # Build message history (last 20 messages for context)
    historico = MensajeAsistente.query.order_by(
        MensajeAsistente.created_at.asc()
    ).limit(30).all()

    api_messages = []
    for m in historico:
        role = m.rol
        if role == 'system':
            continue
        api_messages.append({'role': role, 'content': m.contenido})

    # Get response from Deepseek
    respuesta = chat_with_context(api_messages, None, platform_ctx, knowledge_text)

    # Save assistant message
    ctx_summary = ''
    if docs:
        ctx_summary = f'Fuentes: {len(docs)} documento(s)'
    if platform_ctx:
        ctx_summary += '\n[Usados datos de plataforma]'

    assistant_msg = MensajeAsistente(
        rol='assistant',
        contenido=respuesta,
        contexto_usado=ctx_summary
    )
    db.session.add(assistant_msg)
    db.session.commit()

    return jsonify({
        'respuesta': respuesta,
        'contexto': ctx_summary
    })


@asistente_bp.route('/subir-documento', methods=['POST'])
@login_required
def subir_documento():
    files = request.files.getlist('documento')
    if not files or (len(files) == 1 and not files[0].filename):
        flash('No se selecciono ningun archivo', 'danger')
        return redirect(url_for('asistente.index'))

    from services.storage import tenant_upload_path
    MAX_SIZE = 10 * 1024 * 1024
    procesados = 0
    errores = 0

    for file in files:
        if not file or not file.filename:
            continue
        filename = file.filename
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        if ext not in ('pdf', 'md', 'txt'):
            errores += 1; continue

        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)
        if size > MAX_SIZE:
            errores += 1; continue

        try:
            filepath = tenant_upload_path(
                f'doc_{datetime.utcnow().strftime("%Y%m%d%H%M%S%f")}_{filename}',
                'conocimiento',
            )
            file.save(filepath)
            doc = DocumentoConocimiento(
                nombre=filename, tipo=ext,
                contenido_raw=filepath, num_chunks=0
            )
            db.session.add(doc)
            procesados += 1
        except Exception:
            errores += 1

    db.session.commit()
    if procesados > 0:
        flash(f'{procesados} documento(s) guardado(s).', 'success')
    if errores > 0:
        flash(f'{errores} error(es). Max 10MB, solo PDF/MD/TXT.', 'warning')

    return redirect(url_for('asistente.index'))


@asistente_bp.route('/documento/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar_documento(id):
    doc = DocumentoConocimiento.query.get_or_404(id)
    db.session.delete(doc)
    db.session.commit()
    flash(f'Documento "{doc.nombre}" eliminado', 'success')
    return redirect(url_for('asistente.index'))


@asistente_bp.route('/limpiar-chat', methods=['POST'])
@login_required
def limpiar_chat():
    MensajeAsistente.query.delete()
    db.session.commit()
    flash('Chat limpiado', 'success')
    return redirect(url_for('asistente.index'))


@asistente_bp.route('/configuracion')
@login_required
def configuracion():
    key_configured = bool(os.environ.get('DEEPSEEK_API_KEY', ''))
    docs_count = DocumentoConocimiento.query.count()
    chunks_count = ChunkConocimiento.query.count()
    mensajes_count = MensajeAsistente.query.count()
    return render_template('asistente/configuracion.html',
                           key_configured=key_configured,
                           docs_count=docs_count,
                           chunks_count=chunks_count,
                           mensajes_count=mensajes_count)
