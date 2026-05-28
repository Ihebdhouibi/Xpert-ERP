"""Seed system-default notification templates (garage_id=0).

Called once at startup — idempotent (upserts).
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notification.repository import TemplateRepository

# ---------------------------------------------------------------------------
# Trigger catalog (used by seed AND the /notification-templates/triggers endpoint)
# ---------------------------------------------------------------------------

TRIGGER_CATALOG: list[dict] = [
    {
        "code": "vehicle_ready",
        "label": "Véhicule prêt",
        "description": "Envoyé quand un ordre de réparation passe en statut 'prêt'.",
        "type": "event",
        "channels": ["email", "sms"],
    },
    {
        "code": "unpaid_invoice_reminder_1",
        "label": "Rappel impayé (1er)",
        "description": "Premier rappel après CFG_REMINDER_DELAY_1_DAYS jours de retard.",
        "type": "scheduled",
        "channels": ["email", "sms"],
    },
    {
        "code": "unpaid_invoice_reminder_2",
        "label": "Rappel impayé (2e)",
        "description": "Deuxième rappel après CFG_REMINDER_DELAY_2_DAYS jours de retard.",
        "type": "scheduled",
        "channels": ["email", "sms"],
    },
    {
        "code": "unpaid_invoice_reminder_3",
        "label": "Rappel impayé (3e)",
        "description": "Troisième et dernier rappel après CFG_REMINDER_DELAY_3_DAYS jours.",
        "type": "scheduled",
        "channels": ["email", "sms"],
    },
    {
        "code": "maintenance_due",
        "label": "Entretien à venir",
        "description": "Rappel d'entretien périodique approchant.",
        "type": "scheduled",
        "channels": ["email", "sms"],
    },
    {
        "code": "technical_inspection_due",
        "label": "Contrôle technique à venir",
        "description": "Rappel de contrôle technique approchant.",
        "type": "scheduled",
        "channels": ["email", "sms"],
    },
    {
        "code": "quotation_expiring",
        "label": "Devis expirant",
        "description": "Rappel envoyé quand un devis arrive à expiration.",
        "type": "scheduled",
        "channels": ["email", "sms"],
    },
    {
        "code": "payment_received_receipt",
        "label": "Reçu de paiement",
        "description": "Envoyé après réception d'un paiement.",
        "type": "event",
        "channels": ["email", "sms"],
    },
]

# ---------------------------------------------------------------------------
# Sample contexts — used by the preview endpoint
# ---------------------------------------------------------------------------

SAMPLE_CONTEXTS: dict[str, dict] = {
    "vehicle_ready": {
        "customer_name": "Mohamed Alami",
        "vehicle": "Dacia Logan 2019",
        "registration": "123456-A-01",
        "garage_name": "Xpert Garage",
        "garage_phone": "+212 5 22 00 00 00",
    },
    "unpaid_invoice_reminder_1": {
        "customer_name": "Mohamed Alami",
        "invoice_number": "FA-2024-0042",
        "amount_due": "3 500,00 MAD",
        "due_date": "2024-11-01",
        "garage_name": "Xpert Garage",
        "garage_phone": "+212 5 22 00 00 00",
    },
    "unpaid_invoice_reminder_2": {
        "customer_name": "Mohamed Alami",
        "invoice_number": "FA-2024-0042",
        "amount_due": "3 500,00 MAD",
        "due_date": "2024-11-01",
        "garage_name": "Xpert Garage",
        "garage_phone": "+212 5 22 00 00 00",
    },
    "unpaid_invoice_reminder_3": {
        "customer_name": "Mohamed Alami",
        "invoice_number": "FA-2024-0042",
        "amount_due": "3 500,00 MAD",
        "due_date": "2024-11-01",
        "garage_name": "Xpert Garage",
        "garage_phone": "+212 5 22 00 00 00",
    },
    "maintenance_due": {
        "customer_name": "Mohamed Alami",
        "vehicle": "Dacia Logan 2019",
        "registration": "123456-A-01",
        "due_date": "2025-06-15",
        "garage_name": "Xpert Garage",
        "garage_phone": "+212 5 22 00 00 00",
    },
    "technical_inspection_due": {
        "customer_name": "Mohamed Alami",
        "vehicle": "Dacia Logan 2019",
        "registration": "123456-A-01",
        "due_date": "2025-06-15",
        "garage_name": "Xpert Garage",
        "garage_phone": "+212 5 22 00 00 00",
    },
    "quotation_expiring": {
        "customer_name": "Mohamed Alami",
        "quotation_number": "DEV-2024-0017",
        "total": "8 200,00 MAD",
        "expires_at": "2024-11-15",
        "garage_name": "Xpert Garage",
        "garage_phone": "+212 5 22 00 00 00",
    },
    "payment_received_receipt": {
        "customer_name": "Mohamed Alami",
        "invoice_number": "FA-2024-0042",
        "amount_paid": "3 500,00 MAD",
        "payment_date": "2024-11-10",
        "garage_name": "Xpert Garage",
        "garage_phone": "+212 5 22 00 00 00",
    },
}

# ---------------------------------------------------------------------------
# Default templates
# ---------------------------------------------------------------------------

_TEMPLATES: list[dict] = [
    # ------------------------------------------------------------------
    # vehicle_ready
    # ------------------------------------------------------------------
    {
        "code": "vehicle_ready",
        "channel": "email",
        "subject": "Votre véhicule est prêt — {{ garage_name }}",
        "body": (
            "<p>Bonjour {{ customer_name }},</p>"
            "<p>Nous avons le plaisir de vous informer que votre véhicule "
            "<strong>{{ vehicle }} ({{ registration }})</strong> est prêt à être récupéré.</p>"
            "<p>Nos horaires d'ouverture : du lundi au vendredi de 8h à 18h, samedi de 8h à 13h.</p>"
            "<p>Pour toute question, appelez-nous au {{ garage_phone }}.</p>"
            "<p>Cordialement,<br>{{ garage_name }}</p>"
        ),
    },
    {
        "code": "vehicle_ready",
        "channel": "sms",
        "subject": None,
        "body": (
            "{{ garage_name }} : Votre véhicule {{ vehicle }} ({{ registration }}) est prêt. "
            "Appelez-nous au {{ garage_phone }}."
        ),
    },
    # ------------------------------------------------------------------
    # unpaid_invoice_reminder_1
    # ------------------------------------------------------------------
    {
        "code": "unpaid_invoice_reminder_1",
        "channel": "email",
        "subject": "Rappel de paiement — Facture {{ invoice_number }}",
        "body": (
            "<p>Bonjour {{ customer_name }},</p>"
            "<p>Sauf erreur de notre part, la facture <strong>{{ invoice_number }}</strong> "
            "d'un montant de <strong>{{ amount_due }}</strong>, échue le {{ due_date }}, "
            "reste impayée.</p>"
            "<p>Merci de régulariser cette situation dans les meilleurs délais.</p>"
            "<p>Pour tout renseignement, contactez-nous au {{ garage_phone }}.</p>"
            "<p>Cordialement,<br>{{ garage_name }}</p>"
        ),
    },
    {
        "code": "unpaid_invoice_reminder_1",
        "channel": "sms",
        "subject": None,
        "body": (
            "{{ garage_name }} : Rappel — Facture {{ invoice_number }} de {{ amount_due }} "
            "impayée depuis le {{ due_date }}. Merci de régulariser. {{ garage_phone }}"
        ),
    },
    # ------------------------------------------------------------------
    # unpaid_invoice_reminder_2
    # ------------------------------------------------------------------
    {
        "code": "unpaid_invoice_reminder_2",
        "channel": "email",
        "subject": "2ème rappel de paiement — Facture {{ invoice_number }}",
        "body": (
            "<p>Bonjour {{ customer_name }},</p>"
            "<p>Malgré notre précédent message, la facture <strong>{{ invoice_number }}</strong> "
            "de <strong>{{ amount_due }}</strong> demeure impayée (échéance : {{ due_date }}).</p>"
            "<p>Veuillez procéder au règlement dans les 48 heures ou nous contacter au "
            "{{ garage_phone }} afin de convenir d'un arrangement.</p>"
            "<p>Cordialement,<br>{{ garage_name }}</p>"
        ),
    },
    {
        "code": "unpaid_invoice_reminder_2",
        "channel": "sms",
        "subject": None,
        "body": (
            "{{ garage_name }} : 2ème rappel — Facture {{ invoice_number }} de {{ amount_due }} "
            "toujours impayée. Contactez-nous : {{ garage_phone }}"
        ),
    },
    # ------------------------------------------------------------------
    # unpaid_invoice_reminder_3
    # ------------------------------------------------------------------
    {
        "code": "unpaid_invoice_reminder_3",
        "channel": "email",
        "subject": "Dernier rappel avant contentieux — Facture {{ invoice_number }}",
        "body": (
            "<p>Bonjour {{ customer_name }},</p>"
            "<p>Sans règlement de la facture <strong>{{ invoice_number }}</strong> "
            "(<strong>{{ amount_due }}</strong>, échue le {{ due_date }}) sous 5 jours ouvrés, "
            "nous serons contraints d'engager une procédure de recouvrement.</p>"
            "<p>Nous vous invitons à nous contacter immédiatement au {{ garage_phone }}.</p>"
            "<p>Cordialement,<br>{{ garage_name }}</p>"
        ),
    },
    {
        "code": "unpaid_invoice_reminder_3",
        "channel": "sms",
        "subject": None,
        "body": (
            "{{ garage_name }} : DERNIER rappel — Facture {{ invoice_number }} {{ amount_due }}. "
            "Réglez sous 5j ou appelez {{ garage_phone }}."
        ),
    },
    # ------------------------------------------------------------------
    # maintenance_due
    # ------------------------------------------------------------------
    {
        "code": "maintenance_due",
        "channel": "email",
        "subject": "Entretien de votre véhicule {{ vehicle }} — rappel",
        "body": (
            "<p>Bonjour {{ customer_name }},</p>"
            "<p>L'entretien périodique de votre véhicule <strong>{{ vehicle }} "
            "({{ registration }})</strong> est prévu le <strong>{{ due_date }}</strong>.</p>"
            "<p>Prenez rendez-vous dès maintenant en appelant le {{ garage_phone }}.</p>"
            "<p>Cordialement,<br>{{ garage_name }}</p>"
        ),
    },
    {
        "code": "maintenance_due",
        "channel": "sms",
        "subject": None,
        "body": (
            "{{ garage_name }} : Entretien de votre {{ vehicle }} ({{ registration }}) "
            "prévu le {{ due_date }}. RDV : {{ garage_phone }}"
        ),
    },
    # ------------------------------------------------------------------
    # technical_inspection_due
    # ------------------------------------------------------------------
    {
        "code": "technical_inspection_due",
        "channel": "email",
        "subject": "Contrôle technique de votre {{ vehicle }} — rappel",
        "body": (
            "<p>Bonjour {{ customer_name }},</p>"
            "<p>Le contrôle technique de votre véhicule <strong>{{ vehicle }} "
            "({{ registration }})</strong> arrive à échéance le <strong>{{ due_date }}</strong>.</p>"
            "<p>Contactez-nous au {{ garage_phone }} pour organiser la visite.</p>"
            "<p>Cordialement,<br>{{ garage_name }}</p>"
        ),
    },
    {
        "code": "technical_inspection_due",
        "channel": "sms",
        "subject": None,
        "body": (
            "{{ garage_name }} : CT de votre {{ vehicle }} ({{ registration }}) "
            "à renouveler avant le {{ due_date }}. Appelez {{ garage_phone }}"
        ),
    },
    # ------------------------------------------------------------------
    # quotation_expiring
    # ------------------------------------------------------------------
    {
        "code": "quotation_expiring",
        "channel": "email",
        "subject": "Votre devis {{ quotation_number }} expire bientôt",
        "body": (
            "<p>Bonjour {{ customer_name }},</p>"
            "<p>Votre devis <strong>{{ quotation_number }}</strong> "
            "d'un montant de <strong>{{ total }}</strong> expire le "
            "<strong>{{ expires_at }}</strong>.</p>"
            "<p>Pour valider ou obtenir plus d'informations, contactez-nous au {{ garage_phone }}.</p>"
            "<p>Cordialement,<br>{{ garage_name }}</p>"
        ),
    },
    {
        "code": "quotation_expiring",
        "channel": "sms",
        "subject": None,
        "body": (
            "{{ garage_name }} : Votre devis {{ quotation_number }} ({{ total }}) "
            "expire le {{ expires_at }}. Infos : {{ garage_phone }}"
        ),
    },
    # ------------------------------------------------------------------
    # payment_received_receipt
    # ------------------------------------------------------------------
    {
        "code": "payment_received_receipt",
        "channel": "email",
        "subject": "Reçu de paiement — Facture {{ invoice_number }}",
        "body": (
            "<p>Bonjour {{ customer_name }},</p>"
            "<p>Nous accusons réception de votre règlement de <strong>{{ amount_paid }}</strong> "
            "pour la facture <strong>{{ invoice_number }}</strong> en date du "
            "{{ payment_date }}.</p>"
            "<p>Merci pour votre confiance.</p>"
            "<p>Cordialement,<br>{{ garage_name }}</p>"
        ),
    },
    {
        "code": "payment_received_receipt",
        "channel": "sms",
        "subject": None,
        "body": (
            "{{ garage_name }} : Paiement reçu — {{ amount_paid }} pour la facture "
            "{{ invoice_number }} le {{ payment_date }}. Merci !"
        ),
    },
]


async def seed_templates(db: AsyncSession) -> None:
    """Idempotently insert system default templates (garage_id=0)."""
    for tmpl in _TEMPLATES:
        await TemplateRepository.upsert(
            db,
            garage_id=0,
            code=tmpl["code"],
            channel=tmpl["channel"],
            locale="fr",
            subject=tmpl.get("subject"),
            body=tmpl["body"],
            active=True,
        )
    await db.commit()
