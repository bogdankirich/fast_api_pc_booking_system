from unittest.mock import MagicMock, patch

from app.tasks.email import send_receipt


@patch("app.tasks.email.settings.SMTP_USER", "test_sender@gmail.com")
@patch("app.tasks.email.settings.SMTP_PASSWORD", "super_secret_pass")
@patch("app.tasks.email.smtplib.SMTP_SSL")
def test_send_receipt_success(mock_smtp):

    mock_server = MagicMock()

    mock_smtp.return_value.__enter__.return_value = mock_server

    send_receipt(
        user_email="gamer@test.com",
        pc_id=42,
        start_time="2026-05-01T12:00:00+00:00",
        end_time="2026-05-01T14:00:00+00:00",
        total_cost="150.50",
    )

    mock_server.login.assert_called_once_with(
        "test_sender@gmail.com", "super_secret_pass"
    )

    mock_server.send_message.assert_called_once()

    sent_email = mock_server.send_message.call_args[0][0]

    assert sent_email["To"] == "gamer@test.com"
    assert sent_email["Subject"] == "PC Booking Receipt"

    email_body = sent_email.get_content()
    assert "150.50" in email_body
    assert "42" in email_body
