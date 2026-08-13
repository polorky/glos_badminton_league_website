from django.db import migrations, models


def mens_to_open(apps, schema_editor):
    Division = apps.get_model('league', 'Division')
    Team = apps.get_model('league', 'Team')
    Player = apps.get_model('league', 'Player')
    PendingPlayerVerification = apps.get_model('league', 'PendingPlayerVerification')

    Division.objects.filter(type='Mens').update(type='Open')
    Team.objects.filter(type='Mens').update(type='Open')
    Player.objects.filter(level='Mens').update(level='Open')
    PendingPlayerVerification.objects.filter(level='Mens').update(level='Open')


def open_to_mens(apps, schema_editor):
    Division = apps.get_model('league', 'Division')
    Team = apps.get_model('league', 'Team')
    Player = apps.get_model('league', 'Player')
    PendingPlayerVerification = apps.get_model('league', 'PendingPlayerVerification')

    Division.objects.filter(type='Open').update(type='Mens')
    Team.objects.filter(type='Open').update(type='Mens')
    Player.objects.filter(level='Open').update(level='Mens')
    PendingPlayerVerification.objects.filter(level='Open').update(level='Mens')


class Migration(migrations.Migration):

    dependencies = [
        ('league', '0040_remove_leaguesettings_nomination_window_open_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='division',
            name='type',
            field=models.CharField(
                choices=[('Mixed', 'Mixed'), ('Womens', "Women's"), ('Open', 'Open')],
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name='team',
            name='type',
            field=models.CharField(
                choices=[('Mixed', 'Mixed'), ('Womens', "Women's"), ('Open', 'Open')],
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name='player',
            name='level',
            field=models.CharField(
                choices=[('Womens', "Women's"), ('Open', 'Open')],
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name='pendingplayerverification',
            name='level',
            field=models.CharField(
                choices=[('Mixed', 'Mixed'), ('Womens', "Women's"), ('Open', 'Open')],
                max_length=10,
            ),
        ),
        migrations.RunPython(mens_to_open, reverse_code=open_to_mens),
    ]
