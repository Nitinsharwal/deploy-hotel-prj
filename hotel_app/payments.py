import hashlib
import hmac
import logging

import razorpay
from django.conf import settings

from accounts.models import Booking, Payment

logger = logging.getLogger(__name__)


def _client():
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


def create_order(booking):
    payment = (
        booking.payments.filter(status=Payment.Status.INITIATED).order_by("-created_at").first()
    )
    if payment is None:
        payment = Payment.objects.create(
            booking=booking,
            amount=booking.total_amount,
            method=Payment.Method.CARD,  # placeholder; real method comes from webhook
            status=Payment.Status.INITIATED,
        )

    amount_paise = int(booking.total_amount * 100)  # Razorpay wants amount in paise

    # If we already have an Order id stored, reuse it (idempotent) so a user
    # who reloads the checkout page doesn't accumulate dangling Orders.
    if payment.transaction_id and payment.transaction_id.startswith("order_"):
        order_id = payment.transaction_id
    else:
        order = _client().order.create(
            {
                "amount": amount_paise,
                "currency": settings.RAZORPAY_CURRENCY,
                "receipt": booking.reference,
                "notes": {
                    "booking_reference": booking.reference,
                    "hotel": booking.room.hotel.hotel_name[:64],
                },
            }
        )
        order_id = order["id"]
        payment.transaction_id = order_id
        payment.gateway_response = {"order_created": order}
        payment.save(update_fields=["transaction_id", "gateway_response", "updated_at"])

    return {
        "order_id": order_id,
        "key_id": settings.RAZORPAY_KEY_ID,
        "amount_paise": amount_paise,
        "currency": settings.RAZORPAY_CURRENCY,
        "name": "Noma Hotel",
        "description": f"{booking.room.hotel.hotel_name} · {booking.room.name}",
        "prefill_email": booking.guest_email,
        "prefill_contact": booking.guest_phone or "",
        "booking_reference": booking.reference,
    }


def verify_and_capture(razorpay_order_id, razorpay_payment_id, razorpay_signature):
    """Browser-side success path. Verifies signature locally then marks payment.

    Returns (booking_or_none, status_str) where status_str is one of:
      "ok:confirmed" | "noop:already-success" | "error:<reason>"
    """
    payload = f"{razorpay_order_id}|{razorpay_payment_id}".encode()
    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, razorpay_signature):
        return (None, "error:bad-signature")

    payment = (
        Payment.objects.select_related("booking").filter(transaction_id=razorpay_order_id).first()
    )
    if payment is None:
        return (None, "error:unknown-order")

    if payment.status == Payment.Status.SUCCESS:
        return (payment.booking, "noop:already-success")

    payment.status = Payment.Status.SUCCESS
    payment.transaction_id = (
        razorpay_payment_id  # store the payment id (not the order id) post-capture
    )
    payment.gateway_response = {
        "order_id": razorpay_order_id,
        "payment_id": razorpay_payment_id,
        "signature_verified": True,
    }
    payment.save(update_fields=["status", "transaction_id", "gateway_response", "updated_at"])

    booking = payment.booking
    if booking.status == Booking.Status.PENDING:
        booking.status = Booking.Status.CONFIRMED
        booking.save(update_fields=["status", "updated_at"])

    return (booking, "ok:confirmed")


def construct_event(payload_bytes, sig_header):
    """Verify the Razorpay webhook signature; returns the parsed event or raises."""
    expected = hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode(),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, sig_header or ""):
        raise ValueError("invalid signature")
    import json

    return json.loads(payload_bytes.decode("utf-8"))


def handle_webhook_event(event):
    """Apply side effects for Razorpay events. Idempotent."""
    event_type = event.get("event", "")

    if event_type == "payment.captured":
        entity = event["payload"]["payment"]["entity"]
        order_id = entity.get("order_id")
        payment_id = entity.get("id")
        method = entity.get("method", "card")  # card, upi, netbanking, wallet
        if not order_id:
            return "ignored:no-order"

        payment = Payment.objects.select_related("booking").filter(transaction_id=order_id).first()
        if payment is None:
            # Could happen if the order_id was already replaced by payment_id
            # by verify_and_capture. Try locating via payment_id.
            payment = (
                Payment.objects.select_related("booking").filter(transaction_id=payment_id).first()
            )
        if payment is None:
            logger.warning("Razorpay webhook for unknown order/payment %s/%s", order_id, payment_id)
            return "ignored:unknown"

        if payment.status == Payment.Status.SUCCESS:
            return "noop:already-success"

        # Map Razorpay method names → our Payment.Method choices
        method_map = {
            "card": Payment.Method.CARD,
            "upi": Payment.Method.UPI,
            "netbanking": Payment.Method.NETBANKING,
            "wallet": Payment.Method.WALLET,
        }
        payment.status = Payment.Status.SUCCESS
        payment.method = method_map.get(method, Payment.Method.CARD)
        payment.transaction_id = payment_id or payment.transaction_id
        payment.gateway_response = entity
        payment.save(
            update_fields=["status", "method", "transaction_id", "gateway_response", "updated_at"]
        )

        booking = payment.booking
        if booking.status == Booking.Status.PENDING:
            booking.status = Booking.Status.CONFIRMED
            booking.save(update_fields=["status", "updated_at"])
        return "ok:confirmed"

    if event_type == "payment.failed":
        entity = event["payload"]["payment"]["entity"]
        order_id = entity.get("order_id")
        if not order_id:
            return "ignored:no-order"
        Payment.objects.filter(
            transaction_id=order_id,
            status=Payment.Status.INITIATED,
        ).update(status=Payment.Status.FAILED, gateway_response=entity)
        return "ok:failed"

    if event_type == "refund.processed":
        entity = event["payload"]["refund"]["entity"]
        razorpay_payment_id = entity.get("payment_id")
        Payment.objects.filter(transaction_id=razorpay_payment_id).update(
            status=Payment.Status.REFUNDED,
            gateway_response=entity,
        )
        return "ok:refunded"

    return "ignored:unhandled"


def refund_booking(booking, reason=""):
    """Refund the most recent SUCCESS Payment on a booking, if any."""
    payment = booking.payments.filter(status=Payment.Status.SUCCESS).order_by("-created_at").first()
    if payment is None:
        return ("nothing-to-refund", None)
    if not payment.transaction_id:
        logger.warning("Cannot refund payment %s: missing transaction_id", payment.id)
        return ("error", "missing-transaction-id")

    try:
        refund = _client().payment.refund(
            payment.transaction_id,
            {
                # Razorpay accepts a partial amount; passing None refunds full amount.
                # Notes show up in the dashboard for audit.
                "notes": {"reason": reason or "requested_by_customer"},
            },
        )
    except Exception as exc:
        logger.exception("Razorpay refund failed for payment %s", payment.id)
        return ("error", str(exc)[:200])

    payment.status = Payment.Status.REFUNDED
    payment.gateway_response = {"refund": refund}
    payment.save(update_fields=["status", "gateway_response", "updated_at"])
    return ("refunded", refund.get("id"))
