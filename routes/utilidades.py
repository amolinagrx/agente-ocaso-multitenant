import os
import json
from datetime import datetime
from flask import Blueprint, render_template, request, flash, redirect, url_for, make_response, current_app
from flask_login import login_required
from utils.ai import get_client, DEEPSEEK_CHAT_MODEL
from utils.pdf import generar_pdf_comparativa

utilidades_bp = Blueprint('utilidades', __name__)


@utilidades_bp.route('/')
@login_required
def index():
    return render_template('utilidades/index.html')


@utilidades_bp.route('/comparativa', methods=['POST'])
@login_required
def comparativa():
    files = request.files.getlist('polizas')
    if not files or len(files) < 2:
        flash('Sube al menos 2 archivos PDF para comparar', 'danger')
        return redirect(url_for('utilidades.index'))

    textos = []
    nombres = []

    for f in files:
        if not f.filename:
            continue
        filename = f.filename
        from services.storage import tenant_upload_path
        filepath = tenant_upload_path(
            f'comp_{datetime.utcnow().strftime("%Y%m%d%H%M%S%f")}_{filename}',
            'temporales',
        )
        f.save(filepath)
        from utils.ai import extract_text_from_file
        texto = extract_text_from_file(filepath, filename)

        if texto and not texto.startswith('ERROR'):
            textos.append(texto)
            nombres.append(filename)
        try:
            os.remove(filepath)
        except Exception:
            pass

    if len(textos) < 2:
        flash('No se pudieron extraer textos de al menos 2 archivos', 'danger')
        return redirect(url_for('utilidades.index'))

    # Build prompt for Deepseek
    prompt = """Eres un experto en seguros. Analiza y compara las siguientes polizas de seguro.

Para cada poliza, extrae y estructura la siguiente informacion:
- Compania aseguradora
- Tipo de seguro (auto, hogar, vida, etc.)
- Coberturas principales y sus capitales/limites
- Franquicias
- Prima anual (si aparece)
- Fecha de vigencia
- Beneficios adicionales o exclusiones

Despues, elabora una TABLA COMPARATIVA con todas las polizas lado a lado.
Finalmente, da una recomendacion sobre cual ofrece mejor relacion calidad-precio.

Responde en español, en formato estructurado con secciones claras."""

    knowledge = ''
    for i, (nombre, texto) in enumerate(zip(nombres, textos)):
        knowledge += f'\n\n===== POLIZA {i+1}: {nombre} =====\n{texto[:6000]}'

    client = get_client()
    if not client:
        flash('API de Deepseek no configurada. Configurala en Ajustes.', 'danger')
        return redirect(url_for('utilidades.index'))

    try:
        resp = client.chat.completions.create(
            model=DEEPSEEK_CHAT_MODEL,
            messages=[
                {'role': 'system', 'content': prompt},
                {'role': 'user', 'content': knowledge}
            ],
            temperature=0.2,
            max_tokens=4000
        )
        analisis = resp.choices[0].message.content
    except Exception as e:
        flash(f'Error al consultar Deepseek: {str(e)[:200]}', 'danger')
        return redirect(url_for('utilidades.index'))

    # Guardar resultado en sesion para PDF
    from flask import session
    session['comparativa_data'] = {
        'nombres': nombres,
        'analisis': analisis,
        'fecha': datetime.utcnow().strftime('%d/%m/%Y %H:%M')
    }

    return render_template('utilidades/comparativa.html',
                           nombres=nombres, analisis=analisis)


@utilidades_bp.route('/comparativa/pdf')
@login_required
def descargar_comparativa_pdf():
    from flask import session
    data = session.get('comparativa_data')
    if not data:
        flash('No hay datos de comparativa. Realiza una nueva.', 'warning')
        return redirect(url_for('utilidades.index'))

    return generar_pdf_comparativa(data['nombres'], data['analisis'], data['fecha'])
