import uuid
from django.core.mail import send_mail
from django.conf import settings
from django.utils.text import slugify
from .models import hotels,customers


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
        "Email: reservations@nomahotel.com\n"
        "Phone: +1 (555) 123-4567\n"
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

    send_mail(
        subject,
        text_body,
        settings.EMAIL_HOST_USER,
        [email],
        fail_silently=True,
        html_message=html_body,
    )
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
                                    or call +1 (555) 123-4567.
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
    send_mail(
        subject,
        message,
        settings.EMAIL_HOST_USER,
        [email],
        fail_silently=True,
        html_message=html_message,
    )
    return str(uuid.uuid4())

def generateSlug(hotel_name):
    slug = slugify(hotel_name) + str(uuid.uuid4()).split('-')[0]
    if hotels.objects.filter(hotel_slug = slug).exists():
        return generateSlug(hotel_name)
    return slug

def sendCustomer(customer_email,hotel,payment):
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
    send_mail(
        subject,
        message,
        settings.EMAIL_HOST_USER,
        [customer_email],
        fail_silently=True,
        html_message=html_message,
    )
    return str(uuid.uuid4())
