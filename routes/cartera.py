import os
from datetime import datetime, date
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, jsonify
from flask_login import login_required, current_user
from models import db, CarteraFichero, CarteraPoliza, CarteraBaja, CarteraAlta
from cartera.parser import parse_cartera_xlsx
from cartera.analysis import run_analysis
from utils.ai import get_client, DEEPSEEK_CHAT_MODEL

cartera_bp = Blueprint('cartera', __name__)

MESES = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
         'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

@cartera_bp.route('/')
@login_required
def index():
    ficheros = CarteraFichero.query.order_by(CarteraFichero.anio.desc(), CarteraFichero.mes.desc()).all()

    # KPIs
    ultimo = ficheros[0] if ficheros else None
    variacion_mensual = 0
    variacion_anual = 0
    if ultimo:
        prev = CarteraFichero.query.filter_by(
            mes=ultimo.mes - 1 if ultimo.mes > 1 else 12,
            anio=ultimo.anio if ultimo.mes > 1 else ultimo.anio - 1
        ).first()
        if prev and prev.num_polizas:
            variacion_mensual = round((ultimo.num_polizas - prev.num_polizas) / prev.num_polizas * 100, 1)
        prev_year = CarteraFichero.query.filter_by(mes=ultimo.mes, anio=ultimo.anio - 1).first()
        if prev_year and prev_year.num_polizas:
            variacion_anual = round((ultimo.num_polizas - prev_year.num_polizas) / prev_year.num_polizas * 100, 1)

    # Chart data
    chart_labels = []
    chart_polizas = []
    chart_prima = []
    for f in reversed(ficheros):
        chart_labels.append(f'{MESES[f.mes][:3]} {f.anio}')
        chart_polizas.append(f.num_polizas or 0)
        chart_prima.append(f.prima_neta_total or 0)

    return render_template('cartera/index.html', ficheros=ficheros, meses=MESES,
                           ultimo=ultimo, variacion_mensual=variacion_mensual,
                           variacion_anual=variacion_anual,
                           labels=chart_labels, polizas=chart_polizas, prima=chart_prima)


@cartera_bp.route('/subir', methods=['POST'])
@login_required
def subir():
    file = request.files.get('archivo')
    mes = request.form.get('mes', type=int)
    anio = request.form.get('anio', type=int)
    reemplazar = request.form.get('reemplazar') == '1'

    if not file or not mes or not anio:
        flash('Archivo, mes y ano requeridos', 'danger')
        return redirect(url_for('cartera.index'))

    # Check if already exists
    existente = CarteraFichero.query.filter_by(mes=mes, anio=anio).first()
    if existente and not reemplazar:
        flash(f'Ya existe cartera para {MESES[mes]} {anio}. Marca "Reemplazar" para sobrescribir.', 'warning')
        return redirect(url_for('cartera.index'))

    from services.storage import tenant_upload_path
    filename = f'{anio}-{mes:02d}.xlsx'
    filepath = tenant_upload_path(filename, 'cartera')
    file.save(filepath)

    # Parse
    resultado = parse_cartera_xlsx(filepath)
    if 'error' in resultado:
        flash(f'Error al procesar: {resultado["error"]}', 'danger')
        return redirect(url_for('cartera.index'))

    # Delete old if replacing
    if existente:
        db.session.delete(existente)
        db.session.flush()

    fichero = CarteraFichero(
        mes=mes, anio=anio, nombre_fichero=filename, ruta=filepath,
        hash_md5=resultado['hash_md5'], num_filas=len(resultado['rows']),
        num_polizas=resultado['num_polizas'], prima_neta_total=resultado['prima_neta_total'],
        user_id=current_user.id
    )
    db.session.add(fichero)
    db.session.flush()

    # Save policies
    for p in resultado['rows']:
        db.session.add(CarteraPoliza(fichero_id=fichero.id, **p))

    db.session.commit()

    # Run analysis
    stats = run_analysis(fichero)

    flash(f'{MESES[mes]} {anio}: {resultado["num_polizas"]} polizas, '
          f'{round(resultado["prima_neta_total"], 0)}€ prima. '
          f'{stats["altas"]} altas, {stats["bajas"]} bajas '
          f'({stats["bajas_renumeradas"]} renumeradas, {stats["bajas_sospechosas"]} sospechosas)',
          'success')
    return redirect(url_for('cartera.index'))


@cartera_bp.route('/detalle/<int:id>')
@login_required
def detalle_mes(id):
    fichero = CarteraFichero.query.get_or_404(id)
    altas = CarteraAlta.query.filter_by(mes_hasta=fichero.mes, anio_hasta=fichero.anio).all()
    bajas = CarteraBaja.query.filter_by(mes_hasta=fichero.mes, anio_hasta=fichero.anio).all()
    bajas_renumeradas = [b for b in bajas if b.renumerada]
    bajas_sospechosas = [b for b in bajas if not b.renumerada]
    polizas = fichero.polizas.all()
    # Group by producto
    by_producto = {}
    for p in polizas:
        prod = p.producto or 'Sin producto'
        if prod not in by_producto:
            by_producto[prod] = {'count': 0, 'prima': 0}
        by_producto[prod]['count'] += 1
        by_producto[prod]['prima'] += p.prima_neta

    return render_template('cartera/detalle_mes.html', fichero=fichero, meses=MESES,
                           altas=altas, bajas=bajas, bajas_renumeradas=bajas_renumeradas,
                           bajas_sospechosas=bajas_sospechosas, by_producto=by_producto)


@cartera_bp.route('/bajas-sospechosas')
@login_required
def bajas_sospechosas():
    mes = request.args.get('mes', type=int)
    anio = request.args.get('anio', type=int)
    producto = request.args.get('producto', '')

    query = CarteraBaja.query.filter_by(renumerada=False)
    if mes:
        query = query.filter_by(mes_hasta=mes)
    if anio:
        query = query.filter_by(anio_hasta=anio)
    if producto:
        query = query.filter(CarteraBaja.producto.ilike(f'%{producto}%'))

    bajas = query.order_by(CarteraBaja.prima_neta.desc()).limit(500).all()

    return render_template('cartera/bajas_sospechosas.html', bajas=bajas, meses=MESES,
                           mes=mes, anio=anio, producto=producto)


@cartera_bp.route('/comparativa-anual')
@login_required
def comparativa_anual():
    fichas = CarteraFichero.query.order_by(CarteraFichero.anio, CarteraFichero.mes).all()
    by_year_month = {}
    for f in fichas:
        key = (f.anio, f.mes)
        by_year_month[key] = f

    years = sorted(set(f.anio for f in fichas))
    months_avail = sorted(set(f.mes for f in fichas))

    comp_data = []
    for m in months_avail:
        row = {'mes': m, 'mes_nombre': MESES[m]}
        for y in years:
            f = by_year_month.get((y, m))
            row[y] = f.num_polizas if f else None
            row[f'{y}_prima'] = f.prima_neta_total if f else None
        # Calculate diff between last two years
        if len(years) >= 2:
            y1, y2 = years[-1], years[-2]
            v1 = row.get(y1)
            v2 = row.get(y2)
            if v1 and v2:
                row['diff'] = round((v1 - v2) / v2 * 100, 1) if v2 else 0
            else:
                row['diff'] = None
        comp_data.append(row)

    return render_template('cartera/comparativa_anual.html', comp_data=comp_data,
                           years=years, meses=MESES)


@cartera_bp.route('/eliminar/<int:id>', methods=['POST'])
@login_required
def eliminar(id):
    fichero = CarteraFichero.query.get_or_404(id)
    try:
        from services.storage import validated_tenant_file
        os.remove(validated_tenant_file(fichero.ruta))
    except Exception:
        pass
    db.session.delete(fichero)
    db.session.commit()
    flash('Registro eliminado', 'success')
    return redirect(url_for('cartera.index'))


# ========== PDF routes (redirect to HTML views with print CSS) ==========

@cartera_bp.route('/bajas-sospechosas/pdf')
@login_required
def bajas_pdf():
    """Redirect to HTML view - PDF via browser print."""
    return redirect(url_for('cartera.bajas_sospechosas', mes=request.args.get('mes'),
                           anio=request.args.get('anio'), producto=request.args.get('producto')))


@cartera_bp.route('/comparativa-anual/pdf')
@login_required
def comparativa_anual_pdf():
    return redirect(url_for('cartera.comparativa_anual'))


# ========== Informe Ejecutivo ==========

@cartera_bp.route('/informe')
@login_required
def informe():
    fichas = CarteraFichero.query.order_by(CarteraFichero.anio, CarteraFichero.mes).all()

    if not fichas:
        flash('Sin datos para generar informe', 'warning')
        return redirect(url_for('cartera.index'))

    return render_template('cartera/informe.html', fichas=fichas, meses=MESES,
                           kpis=_calcular_kpis(fichas),
                           resumen=_generar_resumen_ia(fichas))


@cartera_bp.route('/informe/pdf')
@login_required
def informe_pdf():
    """Redirect to HTML informe - PDF via browser print."""
    return redirect(url_for('cartera.informe'))


# ========== Helper functions ==========

def _calcular_kpis(fichas):
    if not fichas: return {}
    last = fichas[-1]
    # Year over year comparison
    prev_year = CarteraFichero.query.filter_by(mes=last.mes, anio=last.anio - 1).first()
    var_polizas = 0
    var_prima = 0
    if prev_year and prev_year.num_polizas:
        var_polizas = round((last.num_polizas - prev_year.num_polizas) / prev_year.num_polizas * 100, 1)
    if prev_year and prev_year.prima_neta_total:
        var_prima = round((last.prima_neta_total - prev_year.prima_neta_total) / prev_year.prima_neta_total * 100, 1)
    return {
        'polizas_last': last.num_polizas,
        'prima_last': last.prima_neta_total,
        'var_polizas_anual': var_polizas,
        'var_prima_anual': var_prima,
    }


def _generar_resumen_ia(fichas):
    kpis = _calcular_kpis(fichas)
    bajas_total = CarteraBaja.query.filter_by(renumerada=False).count()
    last = fichas[-1]

    # Build data for AI
    data_text = f"Ultimo mes: {MESES[last.mes]} {last.anio}. Polizas: {last.num_polizas}. Prima: {last.prima_neta_total:.0f}€.\n"
    data_text += f"Variacion anual: polizas {kpis['var_polizas_anual']:+.1f}%, prima {kpis['var_prima_anual']:+.1f}%.\n"
    data_text += f"Total bajas no renumeradas acumuladas: {bajas_total}.\n"

    client = get_client()
    if not client:
        return {
            'summary': f'Cartera analizada con {len(fichas)} meses de datos. Ultimo mes: {last.num_polizas} polizas, {last.prima_neta_total:.0f}€. Variacion anual: {kpis["var_polizas_anual"]:+.1f}%. Se han detectado {bajas_total} bajas sin renumerar que requieren atencion.',
            'conclusion': f'Se recomienda revisar las {bajas_total} bajas no renumeradas y verificar con Ocaso si corresponden a polizas retiradas sin aviso.'
        }

    prompt = "Eres analista de seguros. Redacta en espanol, tono profesional.\n\n"
    prompt += "1. RESUMEN EJECUTIVO (1 parrafo): Describe el estado de la cartera con los datos proporcionados. Indica si crece o decrece.\n"
    prompt += "2. CONCLUSIONES (1 parrafo): Recomendacion practica sobre las bajas sin renumerar.\n"
    prompt += "Responde en JSON: {\"summary\": \"...\", \"conclusion\": \"...\"}"

    try:
        resp = client.chat.completions.create(
            model=DEEPSEEK_CHAT_MODEL,
            messages=[{'role':'system','content':prompt}, {'role':'user','content':data_text}],
            temperature=0.3, max_tokens=500
        )
        import json, re
        text = resp.choices[0].message.content
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
        return {'summary': text[:500], 'conclusion': text[500:1000] if len(text) > 500 else ''}
    except Exception:
        return {
            'summary': f'Analisis de {len(fichas)} meses. Ultimo: {last.num_polizas} polizas, {last.prima_neta_total:.0f}€. Variacion anual polizas: {kpis["var_polizas_anual"]:+.1f}%.',
            'conclusion': f'Revisar {bajas_total} bajas no renumeradas.'
        }


@cartera_bp.route('/comparativa-meses', methods=['GET', 'POST'])
@login_required
def comparativa_meses():
    mes1 = request.args.get('mes1', type=int) or (date.today().month - 1 if date.today().month > 1 else 12)
    anio1 = request.args.get('anio1', type=int) or (date.today().year - 1 if (date.today().month - 1 if date.today().month > 1 else 12) > date.today().month else date.today().year)
    if request.args.get('mes1'):
        mes1 = request.args.get('mes1', type=int)
        anio1 = request.args.get('anio1', type=int)
        mes2 = request.args.get('mes2', type=int)
        anio2 = request.args.get('anio2', type=int)
    else:
        mes1 = date.today().month
        anio1 = date.today().year - 1
        mes2 = date.today().month
        anio2 = date.today().year

    f1 = CarteraFichero.query.filter_by(mes=mes1, anio=anio1).first()
    f2 = CarteraFichero.query.filter_by(mes=mes2, anio=anio2).first()

    comp = None
    if f1 and f2:
        p1 = CarteraPoliza.query.filter_by(fichero_id=f1.id).count()
        p2 = CarteraPoliza.query.filter_by(fichero_id=f2.id).count()
        altas = CarteraAlta.query.filter_by(mes_hasta=mes2, anio_hasta=anio2).count()
        bajas = CarteraBaja.query.filter_by(mes_hasta=mes2, anio_hasta=anio2, renumerada=False).count()
        bajas_list = CarteraBaja.query.filter_by(mes_hasta=mes2, anio_hasta=anio2, renumerada=False).order_by(CarteraBaja.prima_neta.desc()).all()
        altas_list = CarteraAlta.query.filter_by(mes_hasta=mes2, anio_hasta=anio2).order_by(CarteraAlta.prima_neta.desc()).all()
        comp = {
            'f1': f1, 'f2': f2, 'p1': p1, 'p2': p2,
            'diff': p2 - p1, 'pct': round((p2 - p1) / p1 * 100, 1) if p1 else 0,
            'prima1': f1.prima_neta_total or 0, 'prima2': f2.prima_neta_total or 0,
            'diff_prima': (f2.prima_neta_total or 0) - (f1.prima_neta_total or 0),
            'altas': altas, 'bajas': bajas, 'bajas_list': bajas_list, 'altas_list': altas_list,
        }

    return render_template('cartera/comparativa_meses.html',
                           mes1=mes1, anio1=anio1, mes2=mes2, anio2=anio2,
                           meses=MESES, comp=comp)

@cartera_bp.route('/resumen/<int:id>')
@login_required
def resumen_mes(id):
    f = CarteraFichero.query.get_or_404(id)
    altas = CarteraAlta.query.filter_by(mes_hasta=f.mes, anio_hasta=f.anio).order_by(CarteraAlta.prima_neta.desc()).all()
    bajas = CarteraBaja.query.filter_by(mes_hasta=f.mes, anio_hasta=f.anio, renumerada=False).order_by(CarteraBaja.prima_neta.desc()).all()
    return render_template('cartera/_resumen_mes.html', f=f, altas=altas, bajas=bajas, meses=MESES)
