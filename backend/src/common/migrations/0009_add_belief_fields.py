from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            "common",
            "0008_rename_ix_simulation_submodel_log_additional_info_ix_ssl_additional_info",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="minister",
            name="personal_opinion",
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name="minister",
            name="appointing_group_opinion",
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name="minister",
            name="supporting_group_opinion",
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name="memberofparliament",
            name="personal_opinion",
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name="memberofparliament",
            name="appointing_group_opinion",
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name="memberofparliament",
            name="supporting_group_opinion",
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name="judge",
            name="personal_opinion",
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name="judge",
            name="appointing_group_opinion",
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name="judge",
            name="supporting_group_opinion",
            field=models.FloatField(default=0),
        ),
    ]
