#!/usr/bin/env python3
"""Create the initial tenant, its administrator and the global super-admin."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from models import Tenant, User, db  # noqa: E402
from services.tenant_context import tenant_context  # noqa: E402


def _uuid(raw: str | None) -> str:
    return str(uuid.UUID(raw)) if raw else str(uuid.uuid4())


def _config(name: str) -> str:
    return json.dumps({
        'branding': {'name': name, 'logo': None, 'primary_color': '#b7192e'},
        'locale': 'es-ES',
        'timezone': 'Europe/Madrid',
        'plan': 'standard',
        'features': {},
    }, ensure_ascii=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--tenant-id',
        default=os.environ.get('DEFAULT_TENANT_ID') or os.environ.get('DEFAULT_Tenant_ID'),
    )
    parser.add_argument('--tenant-name', default=os.environ.get('DEFAULT_TENANT_NAME', 'Oficina inicial'))
    parser.add_argument('--subdomain', default=os.environ.get('DEFAULT_TENANT_SUBDOMAIN', 'oficina-inicial'))
    parser.add_argument('--super-admin-email', default=os.environ.get('SUPER_ADMIN_EMAIL'))
    parser.add_argument('--super-admin-password', default=os.environ.get('SUPER_ADMIN_PASSWORD'))
    parser.add_argument('--tenant-admin-email', default=os.environ.get('INITIAL_ADMIN_EMAIL'))
    parser.add_argument('--tenant-admin-password', default=os.environ.get('INITIAL_ADMIN_PASSWORD'))
    args = parser.parse_args()

    if not args.super_admin_email:
        parser.error('Define SUPER_ADMIN_EMAIL o usa --super-admin-email.')
    generated_super_password = not args.super_admin_password
    super_password = args.super_admin_password or secrets.token_urlsafe(24)
    if len(super_password) < 12:
        parser.error('SUPER_ADMIN_PASSWORD debe tener al menos 12 caracteres.')
    if bool(args.tenant_admin_email) != bool(args.tenant_admin_password):
        parser.error('INITIAL_ADMIN_EMAIL e INITIAL_ADMIN_PASSWORD deben indicarse juntos.')

    app = create_app(run_startup_tasks=False)
    with app.app_context():
        tenant = Tenant.query.filter_by(subdomain=args.subdomain).first()
        if tenant is None:
            tenant = Tenant(
                id=_uuid(args.tenant_id),
                name=args.tenant_name,
                subdomain=args.subdomain,
                config_json=_config(args.tenant_name),
                active=True,
            )
            db.session.add(tenant)
            db.session.flush()

        from sqlalchemy import select
        super_statement = (
            select(User)
            .where(User.tenant_id.is_(None), User.email == args.super_admin_email.lower())
            .execution_options(tenant_bypass=True)
        )
        super_admin = db.session.execute(super_statement).scalar_one_or_none()
        if super_admin is None:
            super_admin = User(
                tenant_id=None,
                username=args.super_admin_email.lower(),
                email=args.super_admin_email.lower(),
                nombre='Super administrador',
                is_admin=True,
                is_super_admin=True,
                activo=True,
                permisos='{}',
            )
            super_admin.set_password(super_password)
            db.session.add(super_admin)
        db.session.flush()

        if args.tenant_admin_email:
            email = args.tenant_admin_email.lower()
            with tenant_context(tenant):
                tenant_admin = User.query.filter_by(email=email).first()
                if tenant_admin is None:
                    tenant_admin = User(
                        tenant_id=tenant.id,
                        username=email,
                        email=email,
                        nombre='Administrador',
                        is_admin=True,
                        activo=True,
                        permisos='{}',
                    )
                    tenant_admin.set_password(args.tenant_admin_password)
                    db.session.add(tenant_admin)
                db.session.flush()

        db.session.commit()
        print(f'Tenant inicial: {tenant.name} ({tenant.id}, {tenant.subdomain})')
        print(f'Super-admin: {args.super_admin_email.lower()}')
        if generated_super_password:
            print(f'Contraseña temporal generada: {super_password}')


if __name__ == '__main__':
    main()
