"""
Exporta todos los datos de SQLite a JSON para importarlos en Railway (PostgreSQL).
Uso:
    python exportar_datos.py          # exporta a datos_sqlite.json
    python manage.py loaddata datos_sqlite.json  # importar en Railway
"""
import subprocess, sys

subprocess.run([
    sys.executable, 'manage.py', 'dumpdata',
    '--natural-foreign',
    '--natural-primary',
    '--exclude', 'auth.permission',
    '--exclude', 'contenttypes',
    '--exclude', 'admin.logentry',
    '--exclude', 'axes',
    '--exclude', 'simple_history',
    '--indent', '2',
    '--output', 'datos_sqlite.json',
], check=True)

print("Exportado correctamente a datos_sqlite.json")
print("Para importar en Railway ejecuta:")
print("  python manage.py loaddata datos_sqlite.json")
