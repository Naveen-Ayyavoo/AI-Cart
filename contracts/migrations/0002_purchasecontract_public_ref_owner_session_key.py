"""Add collision-checked readable public_ref and session ownership key to PurchaseContract."""

from django.db import migrations, models

from contracts.access import generate_unique_public_ref


def populate_contract_public_refs(apps, schema_editor):
    PurchaseContract = apps.get_model("contracts", "PurchaseContract")
    for contract in PurchaseContract.objects.all().iterator():
        if not contract.public_ref:
            contract.public_ref = generate_unique_public_ref(
                "PC",
                contract.category,
                PurchaseContract,
                fallback="shopping-request",
            )
            contract.save(update_fields=["public_ref"])


class Migration(migrations.Migration):

    dependencies = [
        ("contracts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="purchasecontract",
            name="owner_session_key",
            field=models.CharField(blank=True, db_index=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="purchasecontract",
            name="public_ref",
            field=models.SlugField(blank=True, db_index=True, max_length=96, null=True),
        ),
        migrations.RunPython(populate_contract_public_refs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="purchasecontract",
            name="public_ref",
            field=models.SlugField(blank=True, db_index=True, max_length=96, unique=True),
        ),
    ]

