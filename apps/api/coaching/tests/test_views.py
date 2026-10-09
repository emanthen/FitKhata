"""HTTP-level integration tests through DRF's APIClient — same reasoning
as every other app's test_views.py: exercises routing/permissions/
serializers together, catching the kind of multipart/request.data
coercion bugs a service-level test alone wouldn't (e.g. BodyMeasurement
create() parsing form fields and files).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import BytesIO

import pytest
from PIL import Image
from rest_framework.test import APIClient

from accounts.models import StaffRole, User
from accounts.tokens import issue_tokens_for_user
from coaching.models import BodyMeasurement, ClassBooking, ClassSchedule, CoachingReport, Exercise
from core.context import system_context
from gyms.models import Gym, Organization
from members.services import register_member

pytestmark = pytest.mark.django_db


def _client_for(user: User, gym: Gym) -> APIClient:
    tokens = issue_tokens_for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}", HTTP_X_GYM_ID=str(gym.pk))
    return client


def _fake_image() -> BytesIO:
    buf = BytesIO()
    Image.new("RGB", (4, 4)).save(buf, format="JPEG")
    buf.seek(0)
    buf.name = "progress.jpg"
    return buf


@pytest.fixture
def setup():
    with system_context():
        org = Organization.objects.create(name="Coaching View Test Org")
        gym = Gym.objects.create(org=org, code="CVT1", name="Coaching View Test Gym")
        owner = User.objects.create_user(phone="+9774000003001", password="x")
        StaffRole.objects.create(user=owner, org=org, gym=gym, role=StaffRole.Role.OWNER)
        front_desk = User.objects.create_user(phone="+9774000003002", password="x")
        StaffRole.objects.create(user=front_desk, org=org, gym=gym, role=StaffRole.Role.FRONT_DESK)
        member = register_member(gym, full_name="View Test Member", phone="+9779800050001")
        exercise = Exercise.objects.filter(muscle_group="legs").first()
    return org, gym, owner, front_desk, member, exercise


def test_exercise_catalog_is_readable_without_auth():
    client = APIClient()
    response = client.get("/api/v1/coaching/exercises/")
    assert response.status_code == 200


def test_record_measurement_with_a_photo_via_multipart(setup):
    _org, gym, _owner, front_desk, member, _exercise = setup
    client = _client_for(front_desk, gym)

    response = client.post(
        "/api/v1/coaching/measurements/",
        {
            "member": str(member.pk),
            "measured_on": "2026-10-01",
            "weight_kg": "80.00",
            "photos": _fake_image(),
            "angle": "front",
        },
        format="multipart",
    )

    assert response.status_code == 201, response.content
    body = response.json()
    assert len(body["photos"]) == 1
    assert body["photos"][0]["url"]  # a signed URL was generated

    with system_context():
        assert BodyMeasurement.objects.filter(member=member, weight_kg=Decimal("80.00")).exists()


def test_workout_log_quick_logger_via_api(setup):
    _org, gym, _owner, front_desk, member, exercise = setup
    client = _client_for(front_desk, gym)

    response = client.post(
        "/api/v1/coaching/workout-logs/",
        {"member": str(member.pk), "exercise": str(exercise.pk), "sets": [{"kg": 40, "reps": 8}]},
        format="json",
    )

    assert response.status_code == 201, response.content
    assert response.json()["exercise_name_en"] == exercise.name_en


def test_class_booking_and_cancel_promotes_waitlist_via_api(setup):
    _org, gym, _owner, front_desk, member, _exercise = setup
    with system_context():
        other_member = register_member(gym, full_name="Second Member", phone="+9779800050002")
        schedule = ClassSchedule.objects.create(
            org=gym.org,
            gym=gym,
            name="API Test Class",
            starts_at="2026-10-10T07:00:00Z",
            capacity=1,
        )

    client = _client_for(front_desk, gym)
    first = client.post(
        "/api/v1/coaching/bookings/",
        {"class_schedule": str(schedule.pk), "member": str(member.pk)},
        format="json",
    )
    second = client.post(
        "/api/v1/coaching/bookings/",
        {"class_schedule": str(schedule.pk), "member": str(other_member.pk)},
        format="json",
    )
    assert first.json()["status"] == "booked"
    assert second.json()["status"] == "waitlist"

    cancel = client.post(f"/api/v1/coaching/bookings/{first.json()['id']}/cancel/")
    assert cancel.status_code == 200

    with system_context():
        assert ClassBooking.objects.get(pk=second.json()["id"]).status == ClassBooking.Status.BOOKED


def test_front_desk_cannot_approve_a_coaching_report(setup):
    _org, gym, _owner, front_desk, member, _exercise = setup
    with system_context():
        report = CoachingReport.objects.create(
            org=gym.org,
            gym=gym,
            member=member,
            week_start=date(2026, 10, 5),
            kind=CoachingReport.Kind.MEMBER,
        )
    client = _client_for(front_desk, gym)
    response = client.post(f"/api/v1/coaching/reports/{report.pk}/approve/")
    assert response.status_code == 403


def test_owner_can_approve_a_coaching_report(setup):
    _org, gym, owner, _front_desk, member, _exercise = setup
    with system_context():
        report = CoachingReport.objects.create(
            org=gym.org,
            gym=gym,
            member=member,
            week_start=date(2026, 10, 5),
            kind=CoachingReport.Kind.MEMBER,
        )
    client = _client_for(owner, gym)
    response = client.post(f"/api/v1/coaching/reports/{report.pk}/approve/")
    assert response.status_code == 200, response.content
    assert response.json()["status"] == "approved"
