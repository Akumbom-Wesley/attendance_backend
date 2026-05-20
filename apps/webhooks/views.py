import hashlib
import hmac
import json
import logging

from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from apps.companies.models import Company
from apps.webhooks.models import WebhookEvent

logger = logging.getLogger(__name__)

SUPPORTED_DOCTYPES = {"Employee", "Company"}


class ERPNextWebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        raw_body = request.body
        signature = request.headers.get("X-Frappe-Signature")

        if not signature:
            return Response({"detail": "Missing signature."}, status=403)

        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError:
            return Response({"detail": "Invalid JSON."}, status=400)

        doctype = payload.get("doctype")
        if doctype not in SUPPORTED_DOCTYPES:
            return Response({"detail": f"Unsupported doctype: {doctype}"}, status=400)

        # Look up company to get webhook_secret
        company_name = payload.get("company") or payload.get("name")
        company = Company.objects.filter(erpnext_doc_name=company_name).first()

        if not company or not self._verify_signature(
            secret=company.webhook_secret,
            raw_body=raw_body,
            signature=signature,
        ):
            return Response({"detail": "Invalid signature."}, status=403)

        # Save the WebhookEvent
        WebhookEvent.objects.create(
            company=company,
            erpnext_doctype=doctype,
            erpnext_doc_name=payload.get("name"),
            payload=payload,
            processed=False,
        )

        return Response({"detail": "Received."}, status=200)

    @staticmethod
    def _verify_signature(secret: str, raw_body: bytes, signature: str) -> bool:
        expected = hmac.new(
            secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)