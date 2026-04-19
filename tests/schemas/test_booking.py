from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.schemas.booking import BookingCreate

now = datetime.now(timezone.utc)


@pytest.mark.parametrize(
    "start_time, end_time, should_raise, expected_error",
    [
        (now + timedelta(hours=1), now + timedelta(hours=2), False, None),
        (
            now - timedelta(hours=1),
            now + timedelta(hours=2),
            True,
            "Time of booking cannot be in a past",
        ),
        (
            now + timedelta(hours=1),
            now + timedelta(hours=1, minutes=5),
            True,
            "Minimal time of booking is 15 minutes",
        ),
    ],
)
def test_booking_create_validation(start_time, end_time, should_raise, expected_error):
    if should_raise:
        with pytest.raises(ValidationError) as exc_info:
            BookingCreate(pc_id=1, start_time=start_time, end_time=end_time)
        assert expected_error in str(exc_info.value)
    else:
        booking = BookingCreate(pc_id=1, start_time=start_time, end_time=end_time)
        assert booking.pc_id == 1
