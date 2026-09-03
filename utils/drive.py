"""Google Drive integration for document storage."""
import os
import io
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

SCOPES = ['https://www.googleapis.com/auth/drive.file']


def _get_drive_service():
    """Build and return Drive service from stored credentials."""
    from models import Configuracion
    creds_json = Configuracion.query.filter_by(clave='drive_credentials').first()
    folder_id = Configuracion.query.filter_by(clave='drive_folder_id').first()

    if not creds_json or not creds_json.valor:
        return None, None

    try:
        creds_dict = json.loads(creds_json.valor)
        credentials = service_account.Credentials.from_service_account_info(
            creds_dict, scopes=SCOPES)
        service = build('drive', 'v3', credentials=credentials)
        folder = folder_id.valor if folder_id else None
        return service, folder
    except (json.JSONDecodeError, Exception) as e:
        print(f'Drive init error: {e}')
        return None, None


def is_drive_configured():
    """Check if Google Drive is configured."""
    s, f = _get_drive_service()
    return s is not None


def upload_to_drive(filepath, filename, folder_id=None):
    """Upload file to Google Drive. Returns drive file ID or None."""
    service, folder = _get_drive_service()
    if not service:
        return None

    target_folder = folder_id or folder
    file_metadata = {'name': filename}
    if target_folder:
        file_metadata['parents'] = [target_folder]

    try:
        media = MediaFileUpload(filepath, resumable=True)
        drive_file = service.files().create(
            body=file_metadata, media_body=media, fields='id'
        ).execute()
        return drive_file.get('id')
    except Exception as e:
        print(f'Drive upload error: {e}')
        return None


def download_from_drive(file_id):
    """Download file from Google Drive. Returns bytes or None."""
    service, _ = _get_drive_service()
    if not service:
        return None

    try:
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        return fh.getvalue()
    except Exception as e:
        print(f'Drive download error: {e}')
        return None


def delete_from_drive(file_id):
    """Delete file from Google Drive."""
    service, _ = _get_drive_service()
    if not service:
        return False
    try:
        service.files().delete(fileId=file_id).execute()
        return True
    except Exception:
        return False


def migrar_documentos_existentes_a_drive(tenant_id: str | None = None) -> dict:
    """Migra todos los documentos locales existentes a Drive (cuando se activa Drive).

    Busca DocumentoCliente y DocumentoSiniestro sin drive_id y con archivo local
    existente, los sube a Drive y guarda el drive_id.

    Si tenant_id es None, migra para todos los tenants (solo superadmin global).
    Devuelve dict con contadores.
    """
    import os
    from pathlib import Path

    if not is_drive_configured():
        return {'ok': False, 'error': 'Drive no configurado (falta drive_credentials)'}

    # Respetar GOOGLE_DRIVE_ENABLED si está definido
    if os.environ.get('GOOGLE_DRIVE_ENABLED', '') not in ('', '1'):
        # Si está explícitamente a 0, no migrar
        if os.environ.get('GOOGLE_DRIVE_ENABLED') == '0':
            return {'ok': False, 'error': 'GOOGLE_DRIVE_ENABLED=0, activa a 1 para migrar'}

    from models import DocumentoCliente, DocumentoSiniestro, db
    from services.tenant_context import tenant_context
    from models import Tenant

    # Determinar tenants a migrar
    if tenant_id:
        tenants = [db.session.get(Tenant, tenant_id)] if db.session.get(Tenant, tenant_id) else []
    else:
        # Global: migrar todos los tenants activos
        tenants = Tenant.query.filter_by(active=True).all()

    total_ok = 0
    total_error = 0
    total_skip = 0

    for tenant in tenants:
        if not tenant:
            continue
        with tenant_context(tenant):
            # DocumentoCliente
            docs_cli = DocumentoCliente.query.filter(
                (DocumentoCliente.drive_id.is_(None) | (DocumentoCliente.drive_id == '')),
                DocumentoCliente.ruta.isnot(None)
            ).all()
            for doc in docs_cli:
                ruta = doc.ruta
                if not ruta or not Path(ruta).is_file():
                    total_skip += 1
                    continue
                try:
                    drive_id = upload_to_drive(ruta, doc.nombre or Path(ruta).name)
                    if drive_id:
                        doc.drive_id = drive_id
                        total_ok += 1
                    else:
                        total_error += 1
                except Exception:
                    total_error += 1

            # DocumentoSiniestro
            docs_sin = DocumentoSiniestro.query.filter(
                (DocumentoSiniestro.drive_id.is_(None) | (DocumentoSiniestro.drive_id == '')),
                DocumentoSiniestro.ruta.isnot(None)
            ).all()
            for doc in docs_sin:
                ruta = doc.ruta
                if not ruta or not Path(ruta).is_file():
                    total_skip += 1
                    continue
                try:
                    drive_id = upload_to_drive(ruta, doc.nombre or Path(ruta).name)
                    if drive_id:
                        doc.drive_id = drive_id
                        total_ok += 1
                    else:
                        total_error += 1
                except Exception:
                    total_error += 1

            db.session.commit()

    return {'ok': True, 'migrados': total_ok, 'errores': total_error, 'omitidos': total_skip}
