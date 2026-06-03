from django.db import migrations, models

# Mapa: código de alérgeno → clase de Bootstrap Icon (sin el prefijo "bi-")
ICONO_MAP = {
    'gluten':   'bi-stack',
    'lacteos':  'bi-droplet-fill',
    'huevo':    'bi-egg-fill',
    'mani':     'bi-brightness-high',
    'soya':     'bi-leaf-fill',
    'nueces':   'bi-tree-fill',
    'mariscos': 'bi-water',
    'pescado':  'bi-water',
    'mostaza':  'bi-sun-fill',
    'apio':     'bi-flower1',
    'sesamo':   'bi-circle-fill',
    'sulfitos': 'bi-lightning-fill',
    'moluscos': 'bi-yin-yang',
    'otro':     'bi-question-diamond-fill',
}


def actualizar_iconos(apps, schema_editor):
    Alergeno = apps.get_model('app_admin', 'Alergeno')
    for codigo, icono_bi in ICONO_MAP.items():
        Alergeno.objects.filter(codigo=codigo).update(icono=icono_bi)


def revertir_iconos(apps, schema_editor):
    pass  # No restaurar emojis en rollback


class Migration(migrations.Migration):

    dependencies = [
        ('app_admin', '0007_seed_alergenos'),
    ]

    operations = [
        # Ampliar el campo antes de insertar valores más largos que 10 chars
        migrations.AlterField(
            model_name='alergeno',
            name='icono',
            field=models.CharField(blank=True, help_text='Emoji o clase Bootstrap Icon', max_length=40),
        ),
        migrations.RunPython(actualizar_iconos, revertir_iconos),
    ]
