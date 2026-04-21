from django.db import migrations

ALERGENOS = [
    ('gluten',   'Gluten',                  '🌾'),
    ('lacteos',  'Lácteos',                 '🥛'),
    ('huevo',    'Huevo',                   '🥚'),
    ('mani',     'Maní / Cacahuate',        '🥜'),
    ('soya',     'Soya',                    '🫘'),
    ('nueces',   'Frutos secos',            '🌰'),
    ('mariscos', 'Mariscos / Crustáceos',   '🦐'),
    ('pescado',  'Pescado',                 '🐟'),
    ('mostaza',  'Mostaza',                 '🟡'),
    ('apio',     'Apio',                    '🌿'),
    ('sesamo',   'Sésamo',                  '⚪'),
    ('sulfitos', 'Sulfitos',                '🍷'),
    ('moluscos', 'Moluscos',                '🦪'),
    ('otro',     'Otro',                    '⚠️'),
]


def seed(apps, schema_editor):
    Alergeno = apps.get_model('app_admin', 'Alergeno')
    for codigo, _, icono in ALERGENOS:
        Alergeno.objects.get_or_create(codigo=codigo, defaults={'icono': icono})


def unseed(apps, schema_editor):
    pass  # no borrar en rollback, podrían estar en uso


class Migration(migrations.Migration):

    dependencies = [
        ('app_admin', '0006_alergeno_ingrediente_porcentaje_merma_and_more'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
