import smtplib
from datetime import datetime
from decimal import Decimal
from email.message import EmailMessage

from app.core.celery_app import celery_app
from app.core.config import settings


@celery_app.task
def send_receipt(
    user_email: str, pc_id: int, start_time: str, end_time: str, total_cost: Decimal
):
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        print("SMTP credentials are not set. Skipping email.")
        return

    try:
        start_dt = datetime.fromisoformat(start_time)
        end_dt = datetime.fromisoformat(end_time)

        start_formatted = start_dt.strftime("%B %d, %Y, %H:%M")
        end_formatted = end_dt.strftime("%B %d, %Y, %H:%M")
    except ValueError:
        start_formatted = start_time
        end_formatted = end_time

    cost_decimal = Decimal(total_cost)

    msg = EmailMessage()
    msg["Subject"] = "PC Booking Receipt"
    msg["From"] = settings.SMTP_USER
    msg["To"] = user_email

    content = (
        f"Thank you for your booking!\n\n"
        f"Here are your order details:\n"
        f"PC ID: {pc_id}\n"
        f"Start Time: {start_formatted}\n"
        f"End Time: {end_formatted}\n"
        f"Total Cost: {cost_decimal:.2f}\n\n"
        f"We look forward to seeing you!"
    )
    msg.set_content(content)

    try:
        with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
        print(f"Receipt successfully sent to {user_email}")
    except Exception as e:
        print(f"Failed to send email to {user_email}. Error: {str(e)}")
