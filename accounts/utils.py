import logging
import os
import uuid

from django.conf import settings
from django.core.mail import send_mail
from django.utils.text import slugify

from .models import hotels

logger = logging.getLogger(__name__)


def get_site_url(request=None) -> str:
    if request is not None:
        return f"{request.scheme}://{request.get_host()}".rstrip("/")
    raw = getattr(settings, "SITE_URL", "").rstrip("/")
    if raw and raw != "http://127.0.0.1:8000":
        return raw

    for host in getattr(settings, "ALLOWED_HOSTS", []):
        host = host.strip()
        if host and not host.startswith(".") and host not in {"localhost", "127.0.0.1", "*"}:
            return f"https://{host}"

    return "http://127.0.0.1:8000"


def sendBookingSlip(booking, request=None):
    """Pass ``request`` from views so email links use the live domain
    (localhost/ngrok/render) instead of the stale SITE_URL env var."""
    from django.template.loader import render_to_string

    site_url = get_site_url(request)
    ctx = {"booking": booking, "site_url": site_url}

    html_body = render_to_string("emails/booking_confirmed.html", ctx)

    p = booking.payments.last()
    text_body = "\n".join(
        [
            "✓ BOOKING CONFIRMED — Noma Hotel",
            "",
            f"Hi {booking.guest_first_name or 'there'},",
            "",
            f"Your stay at {booking.room.hotel.hotel_name} is locked in.",
            f"Reference: {booking.reference}",
            "",
            "── YOUR STAY ───────────────────────",
            f"Hotel     : {booking.room.hotel.hotel_name}",
            f"Room      : {booking.room.name} ({booking.room.get_room_type_display()})",
            f"Location  : {booking.room.hotel.hotel_location}",
            f"Check-in  : {booking.start_date.strftime('%A, %d %b %Y')}",
            f"Check-out : {booking.end_date.strftime('%A, %d %b %Y')}",
            f"Nights    : {booking.nights}",
            f"Guests    : {booking.num_guests}",
            "",
            "── PAYMENT ─────────────────────────",
            f"Rate      : INR {booking.room.base_price} / night",
            f"Subtotal  : INR {booking.total_amount}",
            *(
                [
                    f"Method    : {p.get_method_display()}",
                    f"Txn ID    : {p.transaction_id or '—'}",
                    f"Paid on   : {p.updated_at.strftime('%d %b %Y, %H:%M')}",
                ]
                if p
                else []
            ),
            f"TOTAL PAID: INR {booking.total_amount}",
            "",
            f"View / download slip: {site_url}/account/profile/#bookings",
            "",
            "Before you arrive: bring a valid photo ID and this confirmation.",
            "Cancellations are subject to the hotel's policy.",
            "",
            "— Noma Hotel · nomapvtltd@gmail.com · +91 8221985564",
        ]
    )

    subject = f"✓ Booking confirmed — {booking.room.hotel.hotel_name} ({booking.reference})"
    return _safe_send_mail(subject, text_body, booking.guest_email, html_body)


def sendCustomerWelcome(user, request=None):
    """Welcome a new customer right after they finish registration.

    Pass ``request`` from the registration view so the welcome email's
    "Find your first stay" link points at the same host the user just
    signed up from. Falls back to SITE_URL env / ALLOWED_HOSTS guess
    when there's no request available.
    """
    from django.template.loader import render_to_string

    site_url = get_site_url(request)
    ctx = {
        "user": user,
        "first_name": user.first_name or user.email.split("@")[0],
        "email": user.email,
        "site_url": site_url,
    }
    html_body = render_to_string("emails/welcome_customer.html", ctx)
    text_body = "\n".join(
        [
            f"Hi {ctx['first_name']},",
            "",
            "Welcome to Noma — your account is ready.",
            "",
            f"Find your first stay: {site_url}/",
            "",
            "— Noma Hotel · nomapvtltd@gmail.com",
        ]
    )
    subject = "Welcome to Noma 🎉"
    return _safe_send_mail(subject, text_body, user.email, html_body)


def sendVendorWelcome(vendor, request=None):
    """Welcome a new vendor and point them at their dashboard.

    Pass ``request`` from the vendor-signup view so the "open dashboard"
    button in the email opens the right host (live URL in prod, not
    localhost) without needing SITE_URL set anywhere.
    """
    from django.template.loader import render_to_string

    site_url = get_site_url(request)
    ctx = {
        "vendor": vendor,
        "first_name": vendor.user.first_name or "there",
        "business_name": vendor.business_name,
        "email": vendor.user.email,
        "site_url": site_url,
    }
    html_body = render_to_string("emails/welcome_vendor.html", ctx)
    text_body = "\n".join(
        [
            f"Hi {vendor.business_name},",
            "",
            "Your Noma vendor account is live.",
            "Add your first hotel and start receiving bookings:",
            f"  {site_url}/account/ven_dashboard/",
            "",
            "— Noma Hotel · vendors@nomahotel.com",
        ]
    )
    subject = "Welcome aboard — Noma Vendor portal"
    return _safe_send_mail(subject, text_body, vendor.user.email, html_body)


def sendChargeReminder(charge):
    """Email a vendor that a platform charge is due (or overdue).

    No ``request`` arg here — this is called from the
    ``send_charge_reminders`` management command (cron), where there is
    no HTTP request to derive a host from. get_site_url() falls back to
    SITE_URL env / ALLOWED_HOSTS, so make sure SITE_URL is set in your
    production env (Render/Vercel dashboard) for these reminder mails to
    link to the live site.
    """
    from django.template.loader import render_to_string

    site_url = get_site_url()
    vendor = charge.vendor
    recipient = vendor.user.email
    ctx = {"charge": charge, "vendor": vendor, "site_url": site_url}
    html_body = render_to_string("emails/charge_reminder.html", ctx)

    days = charge.days_until_due
    if days is None:
        urgency = ""
    elif days > 0:
        urgency = f"Due in {days} day{'s' if days != 1 else ''}"
    elif days == 0:
        urgency = "Due today"
    else:
        urgency = f"Overdue by {-days} day{'s' if days != -1 else ''}"

    subject = f"[Noma] {urgency} — ₹{charge.amount} {charge.get_kind_display()}"
    text_body = "\n".join(
        [
            f"Hi {vendor.business_name},",
            "",
            f"This is a reminder for your {charge.get_kind_display().lower()}:",
            f"  Amount    : INR {charge.amount}",
            f"  Due date  : {charge.due_date.strftime('%d %b %Y') if charge.due_date else 'n/a'}",
            f"  Grace ends: {charge.effective_due_date.strftime('%d %b %Y') if charge.effective_due_date else 'n/a'}",
            f"  Status    : {urgency}",
            "",
            f"Pay now from your vendor dashboard: {site_url}/account/ven_dashboard/",
            "",
            "If the charge isn't paid by the end of the grace period, your hotels",
            "will be temporarily hidden from public search until payment is received.",
            "",
            "— Noma Hotel · nomapvtltd@gmail.com",
        ]
    )
    return _safe_send_mail(subject, text_body, recipient, html_body)


def sendChargePaidConfirmation(charge):
    """Email a quick "thanks, payment received" to the vendor."""
    vendor = charge.vendor
    recipient = vendor.user.email
    subject = f"[Noma] Payment received — ₹{charge.amount}"
    text_body = "\n".join(
        [
            f"Hi {vendor.business_name},",
            "",
            f"We've recorded your payment of INR {charge.amount}",
            f"for: {charge.get_kind_display()}{(' — ' + charge.description) if charge.description else ''}.",
            "",
            f"Paid on: {charge.paid_at.strftime('%d %b %Y, %H:%M') if charge.paid_at else 'just now'}",
            "",
            "Thanks for keeping things up to date!",
            "— Noma Hotel",
        ]
    )
    html_body = f"""
    <div style="font-family: -apple-system, Segoe UI, Roboto, sans-serif; max-width:560px; margin:0 auto; padding:24px;">
      <div style="background:#0f766e; color:#fff; padding:18px 22px; border-radius:14px 14px 0 0;">
        <h2 style="margin:0; font-size:20px;">Payment received ✓</h2>
      </div>
      <div style="background:#fff; padding:22px; border:1px solid #e2e8f0; border-top:0; border-radius:0 0 14px 14px;">
        <p>Hi <strong>{vendor.business_name}</strong>,</p>
        <p>We've recorded your payment of <strong>₹ {charge.amount}</strong>
           for <strong>{charge.get_kind_display()}</strong>{(' — ' + charge.description) if charge.description else ''}.</p>
        <p style="color:#64748b; font-size:13px;">
          Paid on {charge.paid_at.strftime('%d %b %Y, %H:%M') if charge.paid_at else 'just now'}
        </p>
        <p>Thanks for keeping things up to date.</p>
        <p style="color:#64748b; font-size:13px; margin-top:24px;">— Noma Hotel</p>
      </div>
    </div>
    """
    return _safe_send_mail(subject, text_body, recipient, html_body)


def sendContactNotification(msg):
    """Email the ops team that a new Contact Us message just came in.

    Ops address falls back to EMAIL_USER (the SMTP login email) so it works
    out of the box without any extra env var. Override with CONTACT_OPS_EMAIL.
    """
    from django.conf import settings as _s

    ops = (
        os.getenv("CONTACT_OPS_EMAIL")
        or getattr(_s, "EMAIL_HOST_USER", "")
        or "nomapvtltd@gmail.com"
    )

    subject = f"[Noma] New contact — {msg.subject or '(no subject)'}"
    text_body = "\n".join(
        [
            "New message from the Contact Us form",
            "",
            f"From    : {msg.first_name} {msg.last_name}",
            f"Email   : {msg.email}",
            f"Subject : {msg.subject or '—'}",
            f"User    : {msg.user.email if msg.user_id else '(not logged in)'}",
            f"IP      : {msg.ip_address or '—'}",
            "",
            "── Message ──────────────────────────",
            msg.message,
            "─────────────────────────────────────",
            "",
            f"View in admin: /admin/accounts/contactmessage/{msg.id}/change/",
        ]
    )
    html_body = f"""
    <div style="font-family: -apple-system, Segoe UI, Roboto, sans-serif; max-width:600px; margin:0 auto;">
      <div style="background:#0f766e; color:#fff; padding:18px 22px; border-radius:14px 14px 0 0;">
        <h2 style="margin:0; font-size:20px;">📬 New contact message</h2>
        <p style="margin:4px 0 0; color:#a7f3d0; font-size:13px;">From {msg.first_name} {msg.last_name}</p>
      </div>
      <div style="background:#fff; padding:22px; border:1px solid #e2e8f0; border-top:0; border-radius:0 0 14px 14px;">
        <table style="width:100%; font-size:14px; border-collapse:collapse;">
          <tr><td style="color:#64748b; padding:4px 0; width:120px;">Email</td><td><strong>{msg.email}</strong></td></tr>
          <tr><td style="color:#64748b; padding:4px 0;">Subject</td><td><strong>{msg.subject or '—'}</strong></td></tr>
          <tr><td style="color:#64748b; padding:4px 0;">Logged in</td><td>{msg.user.email if msg.user_id else '<em>guest</em>'}</td></tr>
          <tr><td style="color:#64748b; padding:4px 0;">IP</td><td style="font-family:monospace; font-size:12px;">{msg.ip_address or '—'}</td></tr>
        </table>
        <div style="background:#f8fafc; border-left:4px solid #0f766e; padding:14px 18px; margin-top:14px; border-radius:0 8px 8px 0;">
          <div style="font-size:11px; color:#64748b; text-transform:uppercase; letter-spacing:0.08em; font-weight:700; margin-bottom:6px;">Message</div>
          <div style="white-space:pre-wrap; line-height:1.6; font-size:14px;">{msg.message}</div>
        </div>
        <p style="margin-top:18px; font-size:12px; color:#64748b;">
          Reply to <a href="mailto:{msg.email}" style="color:#0f766e;">{msg.email}</a> directly,
          or open the admin to mark this thread resolved.
        </p>
      </div>
    </div>
    """
    return _safe_send_mail(subject, text_body, ops, html_body)


def sendContactAck(msg):
    """Acknowledgement email to the person who submitted the form."""
    subject = "Thanks for contacting Noma Hotel"
    text_body = "\n".join(
        [
            f"Hi {msg.first_name},",
            "",
            "Thanks for reaching out — we've received your message and a real",
            "human on our team will get back to you within 1–2 business days.",
            "",
            "For your records, here's a copy of what you sent:",
            "",
            "─────────────────────────────────────",
            msg.message,
            "─────────────────────────────────────",
            "",
            "If your question is urgent, you can also call +91 8221985564.",
            "",
            "— The Noma Team",
        ]
    )
    html_body = f"""
    <div style="font-family: -apple-system, Segoe UI, Roboto, sans-serif; max-width:560px; margin:0 auto; padding:24px;">
      <div style="background:#0f766e; color:#fff; padding:18px 22px; border-radius:14px 14px 0 0;">
        <h2 style="margin:0; font-size:20px;">We got your message ✓</h2>
      </div>
      <div style="background:#fff; padding:22px; border:1px solid #e2e8f0; border-top:0; border-radius:0 0 14px 14px;">
        <p>Hi <strong>{msg.first_name}</strong>,</p>
        <p>Thanks for reaching out — a real human on our team will get back to you within
           <strong>1–2 business days</strong>.</p>
        <p style="color:#64748b; font-size:13px; margin-top:18px;">For your records, here's what you sent:</p>
        <div style="background:#f8fafc; border-left:4px solid #0f766e; padding:14px 18px; border-radius:0 8px 8px 0; font-size:14px; white-space:pre-wrap; line-height:1.6;">{msg.message}</div>
        <p style="font-size:13px; color:#64748b; margin-top:20px;">
          If it's urgent you can also call <a href="tel:+918221985564" style="color:#0f766e;">+91 8221985564</a>.
        </p>
        <p style="font-size:13px; color:#64748b; margin-top:24px;">— The Noma Team</p>
      </div>
    </div>
    """
    return _safe_send_mail(subject, text_body, msg.email, html_body)


def sendForgotPasswordEmail(user, otp, token, request=None):
    from django.template.loader import render_to_string

    site_url = get_site_url(request)
    reset_link = f"{site_url}/account/forgot/reset/{token}/"
    ctx = {
        "user": user,
        "first_name": user.first_name or user.email.split("@")[0],
        "otp": otp,
        "reset_link": reset_link,
        "site_url": site_url,
    }
    html_body = render_to_string("emails/forgot_password.html", ctx)
    text_body = "\n".join([
        f"Hi {ctx['first_name']},",
        "",
        "We received a request to reset your Noma password.",
        "",
        f"Your one-time code: {otp}",
        "(expires in 30 minutes)",
        "",
        "Or click this link to reset directly:",
        f"  {reset_link}",
        "",
        "If you didn't request this, you can ignore this email — your password won't change.",
        "",
        "— Noma Hotel · nomapvtltd@gmail.com",
    ])
    subject = f"Reset your Noma password — code {otp}"
    return _safe_send_mail(subject, text_body, user.email, html_body)


def _safe_send_mail(subject, text_body, recipient, html_body):
    """Fire-and-forget email send. Returns immediately (True) — the SMTP
    work happens on a daemon thread so the HTTP request can return.

    Why this changed: synchronous send_mail() blocks the gunicorn worker
    on socket.connect() — if Gmail is slow or Render's network hiccups,
    the worker hits its 30s timeout and gets SIGKILL'd, returning a 500
    to the user. With a background thread the worker returns in <50ms;
    the email arrives a few seconds later (or doesn't, in which case
    we log it and move on — same as before).

    The thread is `daemon=True` so it dies cleanly when gunicorn restarts
    the worker. A few in-flight emails could be lost on deploy/scale —
    acceptable trade-off for non-critical mail (welcome, OTP, slip).
    Critical mail (payment receipts) should move to a real queue later.
    """
    def _send():
        try:
            send_mail(
                subject,
                text_body,
                settings.EMAIL_HOST_USER,
                [recipient],
                fail_silently=False,
                html_message=html_body,
            )
        except Exception:
            logger.exception("Email send failed (subject=%s, to=%s)", subject, recipient)

    import threading
    threading.Thread(target=_send, daemon=True).start()
    return True


def random_token():
    return str(uuid.uuid4())


def sendEmail(email, token):
    subject = "Welcome to Noma Hotel - Please Verify Your Account"
    verify_url = f"https://sharwal-nitin-hotel.vercel.app/account/verify-account/{token}"

    text_body = (
        "Dear Guest,\n\n"
        "Thank you for choosing Noma Hotel. We're delighted to have you join our community.\n\n"
        "To complete your registration and ensure the security of your account, please verify your email address by clicking the link below:\n\n"
        f"{verify_url}\n\n"
        "This verification link will expire in 24 hours for security reasons.\n\n"
        "If you did not create an account with Noma Hotel, please disregard this email.\n\n"
        "We look forward to welcoming you to an exceptional hospitality experience.\n\n"
        "Best regards,\n"
        "The Noma Hotel Team\n"
        "Email: nomapvtltd@gmail.com\n"
        "Phone: +91 8221985564\n"
        "Website: www.nomahotel.com"
    )

    html_body = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Welcome to Noma Hotel</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: 'Georgia', 'Times New Roman', serif; background-color: #f8f9fa;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #f8f9fa;">
            <tr>
                <td align="center" style="padding: 40px 20px;">
                    <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); overflow: hidden;">
                        <!-- Header -->
                        <tr>
                            <td style="background: linear-gradient(135deg, #1a365d 0%, #2d3748 100%); padding: 30px 40px; text-align: center;">
                                <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 300; letter-spacing: 2px;">NOMA HOTEL</h1>
                                <p style="margin: 8px 0 0; color: #e2e8f0; font-size: 16px; font-weight: 300;">Luxury Redefined</p>
                            </td>
                        </tr>

                        <!-- Content -->
                        <tr>
                            <td style="padding: 40px;">
                                <h2 style="margin: 0 0 20px; color: #1a365d; font-size: 24px; font-weight: 400;">Welcome to Noma Hotel</h2>

                                <p style="margin: 0 0 25px; color: #4a5568; font-size: 16px; line-height: 1.6;">
                                    Dear Guest,<br><br>
                                    Thank you for choosing Noma Hotel. We're delighted to have you join our community of discerning travelers.
                                </p>

                                <p style="margin: 0 0 30px; color: #4a5568; font-size: 16px; line-height: 1.6;">
                                    To complete your registration and ensure the security of your account, please verify your email address by clicking the button below:
                                </p>

                                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                    <tr>
                                        <td align="center" style="padding: 20px 0;">
                                            <a href="{verify_url}" style="display: inline-block; padding: 16px 32px; background: linear-gradient(135deg, #1a365d 0%, #2d3748 100%); color: #ffffff; text-decoration: none; border-radius: 8px; font-size: 16px; font-weight: 600; letter-spacing: 0.5px; box-shadow: 0 4px 15px rgba(26, 54, 93, 0.3);">Verify My Email Address</a>
                                        </td>
                                    </tr>
                                </table>

                                <p style="margin: 30px 0 15px; color: #718096; font-size: 14px; text-align: center;">
                                    Or copy and paste this link into your browser:
                                </p>

                                <p style="margin: 0 0 30px; word-break: break-all; color: #1a365d; font-size: 14px; text-align: center; background-color: #f7fafc; padding: 15px; border-radius: 6px; border: 1px solid #e2e8f0;">
                                    {verify_url}
                                </p>

                                <div style="background-color: #fff5f5; border-left: 4px solid #e53e3e; padding: 20px; margin: 30px 0; border-radius: 0 6px 6px 0;">
                                    <p style="margin: 0; color: #c53030; font-size: 14px; font-weight: 500;">
                                        <strong>Important:</strong> This verification link will expire in 24 hours for security reasons.
                                    </p>
                                </div>

                                <p style="margin: 30px 0 0; color: #4a5568; font-size: 16px; line-height: 1.6;">
                                    If you did not create an account with Noma Hotel, please disregard this email. No further action is required.
                                </p>

                                <p style="margin: 25px 0 0; color: #4a5568; font-size: 16px; line-height: 1.6;">
                                    We look forward to welcoming you to an exceptional hospitality experience.
                                </p>
                            </td>
                        </tr>

                        <!-- Footer -->
                        <tr>
                            <td style="background-color: #1a365d; padding: 30px 40px; text-align: center;">
                                <p style="margin: 0 0 15px; color: #ffffff; font-size: 18px; font-weight: 400;">Best regards,</p>
                                <p style="margin: 0 0 20px; color: #e2e8f0; font-size: 16px;">The Noma Hotel Team</p>

                                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                    <tr>
                                        <td style="padding: 10px 20px;">
                                            <p style="margin: 0; color: #cbd5e1; font-size: 14px; text-align: center;">
                                                📧 <a href="mailto:nomapvtltd@gmail.com" style="color: #cbd5e1; text-decoration: none;">nomapvtltd@gmail.com</a><br>
                                                📞 +91 8221985564<br>
                                                🌐 <a href="https://www.nomahotel.com" style="color: #cbd5e1; text-decoration: none;">www.nomahotel.com</a>
                                            </p>
                                        </td>
                                    </tr>
                                </table>

                                <p style="margin: 20px 0 0; color: #a0aec0; font-size: 12px; border-top: 1px solid #4a5568; padding-top: 20px;">
                                    This email was sent to you because you registered for an account at Noma Hotel.
                                    If you have any questions, please don't hesitate to contact us.
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    _safe_send_mail(subject, text_body, email, html_body)
    return str(uuid.uuid4())


def sendOtp(email, otp):
    subject = "Your Noma Hotel Secure Login Code"
    message = (
        "Dear Guest,\n\n"
        "For your security, we've sent you a one-time password (OTP) to complete your login.\n\n"
        f"Your OTP code is: {otp}\n\n"
        "This code will expire in 10 minutes. Please do not share this code with anyone.\n\n"
        "If you did not request this login attempt, please contact our security team immediately.\n\n"
        "Best regards,\n"
        "The Noma Hotel Security Team\n"
        "Email: nomapvtltd@gmail.com\n"
        "Phone: +91 8221985564"
    )
    html_message = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Your Noma Hotel Login Code</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: 'Georgia', 'Times New Roman', serif; background-color: #f8f9fa;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #f8f9fa;">
            <tr>
                <td align="center" style="padding: 40px 20px;">
                    <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); overflow: hidden;">
                        <!-- Header -->
                        <tr>
                            <td style="background: linear-gradient(135deg, #1a365d 0%, #2d3748 100%); padding: 30px 40px; text-align: center;">
                                <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 300; letter-spacing: 2px;">NOMA HOTEL</h1>
                                <p style="margin: 8px 0 0; color: #e2e8f0; font-size: 16px; font-weight: 300;">Secure Login Verification</p>
                            </td>
                        </tr>

                        <!-- Content -->
                        <tr>
                            <td style="padding: 40px;">
                                <h2 style="margin: 0 0 20px; color: #1a365d; font-size: 24px; font-weight: 400; text-align: center;">Your Security Code</h2>

                                <p style="margin: 0 0 30px; color: #4a5568; font-size: 16px; line-height: 1.6; text-align: center;">
                                    Dear Guest,<br><br>
                                    For your security, we've generated a one-time password to complete your login process.
                                </p>

                                <!-- OTP Display -->
                                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                    <tr>
                                        <td align="center" style="padding: 30px 0;">
                                            <div style="background: linear-gradient(135deg, #1a365d 0%, #2d3748 100%); color: #ffffff; padding: 25px 40px; border-radius: 12px; display: inline-block; box-shadow: 0 6px 20px rgba(26, 54, 93, 0.3);">
                                                <div style="font-size: 36px; font-weight: 700; letter-spacing: 8px; font-family: 'Courier New', monospace;">{otp}</div>
                                            </div>
                                        </td>
                                    </tr>
                                </table>

                                <div style="background-color: #fffbeb; border-left: 4px solid #d97706; padding: 20px; margin: 30px 0; border-radius: 0 6px 6px 0;">
                                    <p style="margin: 0; color: #92400e; font-size: 14px; font-weight: 500;">
                                        <strong>Security Notice:</strong> This code will expire in 10 minutes. Please do not share this code with anyone.
                                    </p>
                                </div>

                                <p style="margin: 30px 0 0; color: #4a5568; font-size: 16px; line-height: 1.6;">
                                    If you did not request this login attempt, please contact our security team immediately at
                                    <a href="mailto:security@nomahotel.com" style="color: #1a365d; text-decoration: underline;">security@nomahotel.com</a>
                                    or call +91 8221985564.
                                </p>
                            </td>
                        </tr>

                        <!-- Footer -->
                        <tr>
                            <td style="background-color: #1a365d; padding: 30px 40px; text-align: center;">
                                <p style="margin: 0 0 15px; color: #ffffff; font-size: 18px; font-weight: 400;">Best regards,</p>
                                <p style="margin: 0 0 20px; color: #e2e8f0; font-size: 16px;">The Noma Hotel Security Team</p>

                                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                    <tr>
                                        <td style="padding: 10px 20px;">
                                            <p style="margin: 0; color: #cbd5e1; font-size: 14px; text-align: center;">
                                                🔒 <a href="nomapvtltd@gmail.com" style="color: #cbd5e1; text-decoration: none;">nomapvtltd@gmail.com</a><br>
                                                📞 +91 8221985564<br>
                                                🌐 <a href="https://sharwal-nitin-hotel.vercel.app/" style="color: #cbd5e1; text-decoration: none;">www.nomahotel.com</a>
                                            </p>
                                        </td>
                                    </tr>
                                </table>

                                <p style="margin: 20px 0 0; color: #a0aec0; font-size: 12px; border-top: 1px solid #4a5568; padding-top: 20px;">
                                    This is an automated security message from Noma Hotel.
                                    Please do not reply to this email.
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    _safe_send_mail(subject, message, email, html_message)
    return str(uuid.uuid4())


def generateSlug(hotel_name):
    slug = slugify(hotel_name) + str(uuid.uuid4()).split("-")[0]
    if hotels.objects.filter(hotel_slug=slug).exists():
        return generateSlug(hotel_name)
    return slug


def sendCustomer(customer_email, hotel, payment):
    subject = "Your Noma Hotel Booking Confirmation"
    message = (
        "Dear Valued Guest,\n\n"
        "Thank you for choosing Noma Hotel. Your booking has been confirmed!\n\n"
        "Booking Details:\n"
        f"Hotel: {hotel}\n"
        f"Payment Status: {payment}\n\n"
        "We are delighted to welcome you to Noma Hotel and look forward to providing you with an exceptional experience.\n\n"
        "Should you require any assistance or have special requests, please don't hesitate to contact our concierge team.\n\n"
        "We look forward to your arrival.\n\n"
        "Warm regards,\n"
        "The Noma Hotel Reservations Team\n"
        "Email: nomapvtltd@gmail.com\n"
        "Phone: +91 8221985564\n"
        "Website: https://sharwal-nitin-hotel.vercel.app/"
    )
    html_message = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Your Noma Hotel Booking Confirmation</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: 'Georgia', 'Times New Roman', serif; background-color: #f8f9fa;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #f8f9fa;">
            <tr>
                <td align="center" style="padding: 40px 20px;">
                    <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); overflow: hidden;">
                        <!-- Header -->
                        <tr>
                            <td style="background: linear-gradient(135deg, #1a365d 0%, #2d3748 100%); padding: 30px 40px; text-align: center;">
                                <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 300; letter-spacing: 2px;">NOMA HOTEL</h1>
                                <p style="margin: 8px 0 0; color: #e2e8f0; font-size: 16px; font-weight: 300;">Booking Confirmed</p>
                            </td>
                        </tr>

                        <!-- Content -->
                        <tr>
                            <td style="padding: 40px;">
                                <div style="text-align: center; margin-bottom: 30px;">
                                    <div style="display: inline-block; background-color: #10b981; color: #ffffff; padding: 15px 25px; border-radius: 50px; font-size: 18px; font-weight: 600;">
                                        ✅ Booking Confirmed
                                    </div>
                                </div>

                                <h2 style="margin: 0 0 20px; color: #1a365d; font-size: 24px; font-weight: 400; text-align: center;">Welcome to Noma Hotel</h2>

                                <p style="margin: 0 0 30px; color: #4a5568; font-size: 16px; line-height: 1.6; text-align: center;">
                                    Dear Valued Guest,<br><br>
                                    Thank you for choosing Noma Hotel. Your booking has been confirmed and we're delighted to welcome you.
                                </p>

                                <!-- Booking Details -->
                                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin: 30px 0;">
                                    <tr>
                                        <td style="padding: 25px; background-color: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0;">
                                            <h3 style="margin: 0 0 20px; color: #1a365d; font-size: 20px; font-weight: 500;">📋 Booking Details</h3>

                                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                                <tr>
                                                    <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0;">
                                                        <strong style="color: #2d3748; font-size: 16px;">Hotel:</strong>
                                                        <span style="color: #4a5568; font-size: 16px; margin-left: 10px;">{hotel}</span>
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0;">
                                                        <strong style="color: #2d3748; font-size: 16px;">Payment Status:</strong>
                                                        <span style="color: #10b981; font-size: 16px; margin-left: 10px; font-weight: 600;">{payment}</span>
                                                    </td>
                                                </tr>
                                            </table>
                                        </td>
                                    </tr>
                                </table>

                                <p style="margin: 30px 0 20px; color: #4a5568; font-size: 16px; line-height: 1.6;">
                                    We are committed to providing you with an exceptional hospitality experience. Our team is preparing for your arrival and ensuring everything is perfect for your stay.
                                </p>

                                <div style="background-color: #e6fffa; border-left: 4px solid #10b981; padding: 20px; margin: 30px 0; border-radius: 0 6px 6px 0;">
                                    <p style="margin: 0; color: #065f46; font-size: 14px; font-weight: 500;">
                                        <strong>Concierge Services:</strong> Should you require any assistance, special requests, or have questions about your stay, our concierge team is available 24/7.
                                    </p>
                                </div>

                                <p style="margin: 30px 0 0; color: #4a5568; font-size: 16px; line-height: 1.6; text-align: center; font-style: italic;">
                                    We look forward to welcoming you and creating unforgettable memories during your stay at Noma Hotel.
                                </p>
                            </td>
                        </tr>

                        <!-- Footer -->
                        <tr>
                            <td style="background-color: #1a365d; padding: 30px 40px; text-align: center;">
                                <p style="margin: 0 0 15px; color: #ffffff; font-size: 18px; font-weight: 400;">Warm regards,</p>
                                <p style="margin: 0 0 20px; color: #e2e8f0; font-size: 16px;">The Noma Hotel Reservations Team</p>

                                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                    <tr>
                                        <td style="padding: 10px 20px;">
                                            <p style="margin: 0; color: #cbd5e1; font-size: 14px; text-align: center;">
                                                📧 <a href="mailto:nomapvtltd@gmail.com" style="color: #cbd5e1; text-decoration: none;">nomapvtltd@gmail.com</a><br>
                                                📞 +91 8221985564<br>
                                                🌐 <a href="https://sharwal-nitin-hotel.vercel.app/" style="color: #cbd5e1; text-decoration: none;">sharwal-nitin-hotel.vercel.app</a>
                                            </p>
                                        </td>
                                    </tr>
                                </table>

                                <p style="margin: 20px 0 0; color: #a0aec0; font-size: 12px; border-top: 1px solid #4a5568; padding-top: 20px;">
                                    This booking confirmation serves as your receipt. Please keep this email for your records.
                                    For any changes to your booking, please contact us as soon as possible.
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    _safe_send_mail(subject, message, customer_email, html_message)
    return str(uuid.uuid4())
