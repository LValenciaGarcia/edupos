# Generated migration — Email unique constraint

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0006_sede_alter_perfil_rol_historicalempleado_empleado'),
    ]

    operations = [
        migrations.RunSQL(
            sql="CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS auth_user_email_unique ON auth_user (email) WHERE email != '';",
            reverse_sql="DROP INDEX IF EXISTS auth_user_email_unique;",
        ),
    ]
