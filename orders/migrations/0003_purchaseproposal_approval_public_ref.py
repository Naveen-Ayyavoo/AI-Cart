"""Add collision-checked readable public_ref to PurchaseProposal and PurchaseApproval."""

from django.db import migrations, models

from contracts.access import generate_unique_public_ref


def populate_order_public_refs(apps, schema_editor):
    PurchaseProposal = apps.get_model("orders", "PurchaseProposal")
    PurchaseApproval = apps.get_model("orders", "PurchaseApproval")

    for proposal in PurchaseProposal.objects.select_related("contract").all().iterator():
        if not proposal.public_ref:
            label = proposal.contract.category if proposal.contract_id else "purchase-item"
            proposal.public_ref = generate_unique_public_ref(
                "PP",
                label,
                PurchaseProposal,
                fallback="purchase-item",
            )
            proposal.save(update_fields=["public_ref"])

    for approval in PurchaseApproval.objects.select_related("proposal", "proposal__contract").all().iterator():
        if not approval.public_ref:
            label = (
                approval.proposal.contract.category
                if approval.proposal_id and approval.proposal.contract_id
                else "purchase-approval"
            )
            approval.public_ref = generate_unique_public_ref(
                "PA",
                label,
                PurchaseApproval,
                fallback="purchase-approval",
            )
            approval.save(update_fields=["public_ref"])


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0002_alter_purchaseproposal_payee_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="purchaseproposal",
            name="public_ref",
            field=models.SlugField(blank=True, db_index=True, max_length=96, null=True),
        ),
        migrations.AddField(
            model_name="purchaseapproval",
            name="public_ref",
            field=models.SlugField(blank=True, db_index=True, max_length=96, null=True),
        ),
        migrations.RunPython(populate_order_public_refs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="purchaseproposal",
            name="public_ref",
            field=models.SlugField(blank=True, db_index=True, max_length=96, unique=True),
        ),
        migrations.AlterField(
            model_name="purchaseapproval",
            name="public_ref",
            field=models.SlugField(blank=True, db_index=True, max_length=96, unique=True),
        ),
    ]

