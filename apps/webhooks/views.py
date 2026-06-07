import base64
import hashlib
import hmac
import json
import logging

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from apps.companies.models import Company
from apps.webhooks.models import WebhookEvent
from apps.webhooks.tasks import process_webhook_event

logger = logging.getLogger(__name__)

SUPPORTED_DOCTYPES = {"Employee", "Company"}


@method_decorator(csrf_exempt, name="dispatch")
class ERPNextWebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        raw_body = request.body
        signature = request.headers.get("X-Frappe-Webhook-Signature")

        if not signature:
            return Response({"detail": "Missing signature."}, status=403)

        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError:
            return Response({"detail": "Invalid JSON."}, status=400)

        doctype = payload.get("doctype")
        if doctype not in SUPPORTED_DOCTYPES:
            return Response({"detail": f"Unsupported doctype: {doctype}"}, status=400)

        company_name = payload.get("company") or payload.get("name")
        company = (
            Company.objects.filter(erpnext_doc_name=company_name).first()
            or Company.objects.filter(name=company_name).first()
        )

        if not company or not self._verify_signature(
            secret=company.webhook_secret,
            raw_body=raw_body,
            signature=signature,
        ):
            return Response({"detail": "Invalid signature."}, status=403)

        event = WebhookEvent.objects.create(
            company=company,
            erpnext_doctype=doctype,
            erpnext_doc_name=payload.get("name"),
            payload=payload,
            processed=False,
        )

        process_webhook_event.delay(event.id)

        return Response({"detail": "Received."}, status=200)

    @staticmethod
    def _verify_signature(secret: str, raw_body: bytes, signature: str) -> bool:
        expected = base64.b64encode(
            hmac.new(
                secret.encode("utf-8"),
                raw_body,
                hashlib.sha256,
            ).digest()
        ).decode("utf-8")
        return hmac.compare_digest(expected, signature)
