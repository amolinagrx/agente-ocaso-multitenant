#!/usr/bin/env python3
"""Rebuild an existing SQLite database as a tenant-aware database.

The source database is never edited in place. A timestamped backup and a new
database are created first; the new file replaces the source only after
SQLite's foreign-key integrity check succeeds.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import uuid

from sqlalchemy import create_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models import db  # noqa: E402


def _default_database() -> Path:
    database_url = os.environ.get('DATABASE_URL')
    if database_url and database_url.startswith('sqlite:///'):
        return Path(database_url.removeprefix('sqlite:///')).expanduser().resolve()
    return Path(os.environ.get('DATA_DIR', '/data')).joinpath('ocaso.db').resolve()


def _validated_uuid(raw: str | None) -> str:
    value = raw or str(uuid.uuid4())
    return str(uuid.UUID(value))


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _table_names(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    )
    return {row[0] for row in rows}


def _columns(connection: sqlite3.Connection, table_name: str) -> list[str]:
    return [row[1] for row in connection.execute(f'PRAGMA table_info({_quote(table_name)})')]


def _already_multitenant(connection: sqlite3.Connection) -> bool:
    names = _table_names(connection)
    return 'tenants' in names and 'tenant_id' in _columns(connection, 'users')


def _copy_legacy_uploads(database: Path, uploads_root: Path, tenant_id: str) -> int:
    mappings = (
        ('documentos_cliente', 'ruta'),
        ('documentos_siniestro', 'ruta'),
        ('cartera_ficheros', 'ruta'),
        ('cartera', 'ruta_archivo'),
    )
    tenant_root = uploads_root.resolve() / tenant_id / 'legacy'
    copied = 0
    connection = sqlite3.connect(database)
    try:
        names = _table_names(connection)
        for table, column in mappings:
            if table not in names or column not in _columns(connection, table):
                continue
            rows = connection.execute(
                f'SELECT id, {_quote(column)} FROM {_quote(table)} '
                f'WHERE {_quote(column)} IS NOT NULL AND {_quote(column)} != ?',
                ('',),
            ).fetchall()
            for row_id, raw_path in rows:
                source = Path(raw_path).expanduser()
                if not source.is_file():
                    continue
                try:
                    source.resolve().relative_to((uploads_root.resolve() / tenant_id))
                    continue
                except ValueError:
                    pass
                destination_dir = tenant_root / table
                destination_dir.mkdir(parents=True, exist_ok=True)
                destination = destination_dir / f'{row_id}_{source.name}'
                shutil.copy2(source, destination)
                connection.execute(
                    f'UPDATE {_quote(table)} SET {_quote(column)} = ? WHERE id = ?',
                    (str(destination), row_id),
                )
                copied += 1
        connection.commit()
    finally:
        connection.close()
    return copied


def migrate(
    database: Path,
    tenant_id: str,
    tenant_name: str,
    subdomain: str,
    uploads_root: Path | None = None,
) -> Path | None:
    if not database.exists():
        raise FileNotFoundError(f'No existe la base de datos: {database}')

    source = sqlite3.connect(database)
    source.row_factory = sqlite3.Row
    try:
        if _already_multitenant(source):
            print('La base de datos ya usa el esquema multi-tenant; no se hicieron cambios.')
            return None

        source.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        backup = database.with_name(f'{database.name}.{timestamp}.bak')
        with sqlite3.connect(backup) as backup_connection:
            source.backup(backup_connection)

        temporary = database.with_name(f'.{database.name}.{timestamp}.migrating')
        if temporary.exists():
            temporary.unlink()

        engine = create_engine(f'sqlite:///{temporary}')
        db.metadata.create_all(engine)
        engine.dispose()

        target = sqlite3.connect(temporary)
        try:
            target.execute('PRAGMA foreign_keys = OFF')
            config = json.dumps({
                'branding': {'name': tenant_name, 'logo': None, 'primary_color': '#b7192e'},
                'locale': 'es-ES',
                'timezone': 'Europe/Madrid',
                'plan': 'standard',
                'features': {},
            }, ensure_ascii=False)
            target.execute(
                'INSERT INTO tenants (id, name, subdomain, config_json, created_at, active) '
                'VALUES (?, ?, ?, ?, ?, 1)',
                (tenant_id, tenant_name, subdomain, config, datetime.now(timezone.utc).isoformat()),
            )

            source_tables = _table_names(source)
            copied_rows = 0
            for table in db.metadata.sorted_tables:
                name = table.name
                if name == 'tenants' or name not in source_tables:
                    continue

                source_columns = _columns(source, name)
                target_columns = [column.name for column in table.columns]
                common = [column for column in target_columns if column in source_columns]
                add_tenant = 'tenant_id' in target_columns and 'tenant_id' not in source_columns
                migration_defaults = {
                    'is_super_admin': 0,
                }
                defaulted = [
                    column for column in target_columns
                    if column not in source_columns and column in migration_defaults
                ]
                insert_columns = common + (['tenant_id'] if add_tenant else []) + defaulted
                if not insert_columns:
                    continue

                selected = ', '.join(_quote(column) for column in common)
                rows = source.execute(f'SELECT {selected} FROM {_quote(name)}').fetchall()
                placeholders = ', '.join('?' for _ in insert_columns)
                insert_sql = (
                    f'INSERT INTO {_quote(name)} '
                    f'({", ".join(_quote(column) for column in insert_columns)}) '
                    f'VALUES ({placeholders})'
                )
                values = []
                for row in rows:
                    item = [row[column] for column in common]
                    if add_tenant:
                        item.append(tenant_id)
                    item.extend(migration_defaults[column] for column in defaulted)
                    values.append(item)
                if values:
                    target.executemany(insert_sql, values)
                    copied_rows += len(values)

            target.commit()
            target.execute('PRAGMA foreign_keys = ON')
            failures = target.execute('PRAGMA foreign_key_check').fetchall()
            if failures:
                raise RuntimeError(f'Falló la validación de claves foráneas: {failures[:5]}')
        except Exception:
            target.close()
            temporary.unlink(missing_ok=True)
            raise
        else:
            target.close()

        source.close()
        source = None
        original_mode = database.stat().st_mode
        os.replace(temporary, database)
        os.chmod(database, original_mode)
        uploads_root = uploads_root or database.parent / 'uploads'
        copied_uploads = _copy_legacy_uploads(database, uploads_root, tenant_id)
        print(f'Migración completada: {copied_rows} filas asignadas al tenant {tenant_id}.')
        print(f'Uploads copiados a {uploads_root / tenant_id}: {copied_uploads}.')
        print(f'Backup recuperable: {backup}')
        return backup
    finally:
        if source is not None:
            source.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=_default_database())
    parser.add_argument(
        '--tenant-id',
        default=os.environ.get('DEFAULT_TENANT_ID') or os.environ.get('DEFAULT_Tenant_ID'),
    )
    parser.add_argument('--tenant-name', default=os.environ.get('DEFAULT_TENANT_NAME', 'Oficina inicial'))
    parser.add_argument('--subdomain', default=os.environ.get('DEFAULT_TENANT_SUBDOMAIN', 'oficina-inicial'))
    parser.add_argument('--uploads-root', type=Path, default=None)
    args = parser.parse_args()

    tenant_id = _validated_uuid(args.tenant_id)
    migrate(
        args.database.expanduser().resolve(), tenant_id, args.tenant_name,
        args.subdomain, args.uploads_root,
    )


if __name__ == '__main__':
    main()
