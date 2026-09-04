#!/usr/bin/env python3
"""
Agente local para Brother ADS-1300 — expone http://localhost:8765/scan
para que la ficha de cliente pueda escanear directamente al navegador.

Uso en el PC de la oficina (conectado por USB al ADS-1300):
    python3 brother_scan_agent.py
    # opcional: python3 brother_scan_agent.py --port 8765 --host 127.0.0.1

Requisitos:
    pip install flask flask-cors pillow
    # Linux: sudo apt install sane sane-utils ghostscript
    # Windows: instalar driver Brother + iPrint&Scan (WIA) o NAPS2

Flujo:
    1. El usuario abre la ficha de un cliente en Agentes Élite y pulsa "Escanear con Brother".
    2. El navegador hace POST http://localhost:8765/scan
    3. El agente dispara el escáner y devuelve el PDF.
    4. El navegador lo inyecta en el input de "Documentos" y hace submit a /clientes/<id>/subir-documento.

El agente NO necesita credenciales de la app; el navegador ya tiene la sesión y el cliente.id.
"""

from __future__ import annotations

import argparse
import io
import os
import platform
import shutil
import subprocess
import tempfile

try:
    from flask import Flask, jsonify, request, send_file
    from flask_cors import CORS
except ImportError:
    print("Falta Flask. Instala: pip install flask flask-cors pillow")
    raise

try:
    from PIL import Image
except ImportError:
    Image = None  # type: ignore


app = Flask(__name__)
# Permitir que https://gestion.* haga fetch a http://localhost:8765
CORS(app, resources={r"/*": {"origins": "*"}})


def _scan_with_scanimage(duplex: bool = False) -> bytes | None:
    """Intenta escanear con `scanimage` (SANE). Devuelve PDF en bytes o None."""
    if not shutil.which("scanimage"):
        return None
    # Detectar escáner
    try:
        out = subprocess.run(["scanimage", "-L"], capture_output=True, text=True, timeout=10)
        if "No scanners were identified" in (out.stdout + out.stderr):
            return None
    except Exception:
        return None

    # Escanear a TIFF temporal y convertir a PDF
    with tempfile.TemporaryDirectory() as tmpdir:
        tiff_path = os.path.join(tmpdir, "scan.tiff")
        pdf_path = os.path.join(tmpdir, "scan.pdf")
        cmd = [
            "scanimage",
            "--resolution", "300",
            "--mode", "Color",
            "--format", "tiff",
        ]
        if duplex:
            # ADS-1300 es simplex; si es el 1300 no tiene duplex, pero lo dejamos
            cmd += ["--source", "ADF Duplex"]
        try:
            with open(tiff_path, "wb") as f:
                subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, timeout=60, check=True)
            if Image is None:
                # Sin Pillow, intentar con tiff2pdf si existe
                if shutil.which("tiff2pdf"):
                    subprocess.run(["tiff2pdf", "-o", pdf_path, tiff_path], check=True, timeout=20)
                    with open(pdf_path, "rb") as pf:
                        return pf.read()
                return None
            # Convertir TIFF -> PDF con Pillow
            im = Image.open(tiff_path)
            # Pillow puede abrir multipage TIFF; guardamos como PDF
            # Si es multipage, Pillow lo maneja como sequence
            try:
                im.save(pdf_path, "PDF", resolution=300.0)
            except Exception:
                # Fallback: convertir a RGB y guardar
                if im.mode in ("RGBA", "P", "LA"):
                    im = im.convert("RGB")
                im.save(pdf_path, "PDF", resolution=300.0)
            with open(pdf_path, "rb") as pf:
                return pf.read()
        except subprocess.CalledProcessError as e:
            print(f"scanimage error: {e.stderr.decode() if e.stderr else e}")
            return None
        except Exception as e:
            print(f"scan error: {e}")
            return None


def _scan_with_wia() -> tuple[bytes | None, str]:
    """Intenta escanear con WIA en Windows. Devuelve (bytes, error_msg)."""
    if platform.system() != "Windows":
        return None, "WIA solo en Windows"
    try:
        import win32com.client  # type: ignore
    except ImportError:
        return None, "Falta pywin32. Ejecuta en esa misma ventana: pip install pywin32  (o reinstala con el .bat actualizado)"
    try:
        mgr = win32com.client.Dispatch("WIA.DeviceManager")
        if mgr.DeviceInfos.Count == 0:
            return None, "No se detectó ningún escáner en Windows. Abre 'Escáneres y cámaras' y verifica que aparezca Brother ADS-1300. Reinstala el driver completo de Brother."
        # Buscar Brother ADS-1300
        device = None
        for i in range(1, mgr.DeviceInfos.Count + 1):
            info = mgr.DeviceInfos.Item(i)
            try:
                name = info.Properties("Name").Value
            except Exception:
                name = str(info)
            if "Brother" in name or "ADS-1300" in name or "ADS" in name:
                device = info.Connect()
                break
        if device is None:
            device = mgr.DeviceInfos.Item(1).Connect()
        item = device.Items.Item(1)
        try:
            item.Properties("3088").Value = 1  # FEEDER
            item.Properties("6146").Value = 2  # Color
            item.Properties("6147").Value = 300
            item.Properties("6148").Value = 300
        except Exception:
            pass
        wia = win32com.client.Dispatch("WIA.CommonDialog")
        # Intentar sin diálogo para ADF; si falla, probar con diálogo
        img = None
        try:
            img = item.Transfer("{B96B3CAB-0728-11D3-9D7B-0000F81EF32E}")  # wiaFormatJPEG
        except Exception:
            img = wia.ShowAcquireImage(0, 0, 0x4, "{00000000-0000-0000-0000-000000000000}", False, True)
        if img is None:
            return None, "El escáner no respondió o se canceló. Coloca un documento en el ADF y prueba de nuevo. Como alternativa, usa Brother iPrint&Scan > Scan to File y luego súbelo con \"Subir\"."
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = tmp.name
        img.SaveFile(tmp_path)
        if Image is not None:
            im = Image.open(tmp_path)
            pdf_buf = io.BytesIO()
            if im.mode in ("RGBA", "P"):
                im = im.convert("RGB")
            im.save(pdf_buf, "PDF", resolution=300.0)
            os.unlink(tmp_path)
            return pdf_buf.getvalue(), ""
        with open(tmp_path, "rb") as f:
            data = f.read()
        os.unlink(tmp_path)
        return data, ""
    except Exception as e:
        # Limpiar mensaje COM genérico 0x80020009
        msg = str(e)
        if "0x80020009" in msg or "-2147352567" in msg:
            msg = "El escáner está ocupado, no responde o el driver WIA no está listo. Cierra iPrint&Scan/ControlCenter, verifica que el ADS-1300 aparezca en 'Escáneres y cámaras' y prueba de nuevo."
        return None, msg


@app.route("/status", methods=["GET"])
def status():
    has_scanimage = bool(shutil.which("scanimage"))
    has_wia = False
    wia_error = None
    if platform.system() == "Windows":
        try:
            import win32com.client  # noqa: F401
            has_wia = True
        except ImportError as e:
            wia_error = str(e)
    # Intentar listar dispositivos WIA si es Windows
    wia_devices = []
    if has_wia:
        try:
            import win32com.client
            mgr = win32com.client.Dispatch("WIA.DeviceManager")
            for i in range(1, mgr.DeviceInfos.Count + 1):
                info = mgr.DeviceInfos.Item(i)
                try:
                    name = info.Properties("Name").Value
                except Exception:
                    name = str(info)
                wia_devices.append(name)
        except Exception as e:
            wia_error = str(e)
    return jsonify({
        "ok": True,
        "scanner": "Brother ADS-1300",
        "platform": platform.system(),
        "backends": {
            "scanimage": has_scanimage,
            "wia": has_wia,
            "wia_error": wia_error,
            "wia_devices": wia_devices,
        },
        "hint": "Conecta el ADS-1300 por USB y ten el driver Brother instalado. En Linux instala 'sane sane-utils' y ejecuta 'scanimage -L'."
    })


@app.route("/scan", methods=["POST", "GET"])
def scan():
    duplex = request.args.get("duplex") == "1" or (request.json or {}).get("duplex") if request.is_json else False

    # En Windows solo WIA; en Linux/macOS solo scanimage. No mezclar mensajes.
    if platform.system() == "Windows":
        data, wia_err = _scan_with_wia()
        if data is not None:
            pass  # ok
        else:
            return jsonify({
                "ok": False,
                "error": wia_err or "No se pudo escanear. Verifica que el ADS-1300 esté conectado por USB, encendido y aparezca en 'Escáneres y cámaras'.",
                "hint": "Prueba Brother iPrint&Scan > Scan to File y luego súbelo con 'Subir'. Diagnóstico: http://127.0.0.1:8765/status",
            }), 500
    else:
        data = _scan_with_scanimage(duplex=bool(duplex))
        if data is None:
            has_scanimage = bool(shutil.which("scanimage"))
            if has_scanimage:
                return jsonify({"ok": False, "error": "scanimage no detectó el escáner. Ejecuta 'scanimage -L' en la terminal y verifica que aparezca Brother ADS-1300. Instala con: sudo apt install sane sane-utils"}, 500)
            return jsonify({"ok": False, "error": "scanimage no instalado. En Linux instala: sudo apt install sane sane-utils"}, 500)

    is_pdf = data[:4] == b"%PDF"
    mimetype = "application/pdf" if is_pdf else "image/jpeg"
    ext = "pdf" if is_pdf else "jpg"
    return send_file(
        io.BytesIO(data),
        mimetype=mimetype,
        as_attachment=False,
        download_name=f"escaneo_brother_{ext}",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agente Brother ADS-1300 para Agentes Élite")
    parser.add_argument("--host", default="127.0.0.1", help="Host (default 127.0.0.1, solo local)")
    parser.add_argument("--port", type=int, default=8765, help="Puerto (default 8765)")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    print(f"Agente Brother ADS-1300 escuchando en http://{args.host}:{args.port}")
    print("Abre la ficha de un cliente en Agentes Élite y pulsa 'Escanear con Brother'.")
    print("Deja esta ventana abierta mientras uses el escáner.")
    app.run(host=args.host, port=args.port, debug=args.debug)
