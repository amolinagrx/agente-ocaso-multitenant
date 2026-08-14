import sqlite3

from scripts.migrate_to_multitenant import migrate


def test_legacy_migration_creates_backup_and_assigns_default_tenant(tmp_path):
    database = tmp_path / 'ocaso.db'
    connection = sqlite3.connect(database)
    connection.executescript('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username VARCHAR(80) NOT NULL UNIQUE,
            password VARCHAR(200) NOT NULL
        );
        CREATE TABLE clientes (
            id INTEGER PRIMARY KEY,
            nombre VARCHAR(200) NOT NULL,
            dni VARCHAR(20) UNIQUE
        );
        INSERT INTO users (id, username, password) VALUES (1, 'admin', 'hash');
        INSERT INTO clientes (id, nombre, dni) VALUES (1, 'Legacy', 'DNI-1');
    ''')
    connection.commit()
    connection.close()

    tenant_id = '11111111-1111-4111-8111-111111111111'
    backup = migrate(database, tenant_id, 'Legacy', 'legacy', tmp_path / 'uploads')

    assert backup is not None and backup.is_file()
    migrated = sqlite3.connect(database)
    assert migrated.execute('SELECT id FROM tenants').fetchone()[0] == tenant_id
    assert migrated.execute('SELECT tenant_id FROM users').fetchone()[0] == tenant_id
    assert migrated.execute('SELECT tenant_id FROM clientes').fetchone()[0] == tenant_id
    assert migrated.execute('PRAGMA foreign_key_check').fetchall() == []
    migrated.close()
