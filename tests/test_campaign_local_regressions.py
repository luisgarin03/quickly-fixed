"""Production regressions; all email delivery is mocked."""
from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app import sender
from app.queue_logic import _next_available_send_time_today
from app.database import get_db
from app.models import GmailAccount
from app.routers.campaigns import router
from tests.conftest import (
    make_campaign, make_campaign_inbox, make_campaign_lead, make_inbox,
    make_lead, make_sequence,
)


async def test_send_test_uses_selected_inbox_gmail_account(session, monkeypatch):
    campaign = await make_campaign(session)
    inbox = await make_inbox(session, email="alias@example.com")
    other = await make_inbox(session, email="other@example.com")
    await make_campaign_inbox(session, campaign.id, other.id, position=1)
    await make_campaign_inbox(session, campaign.id, inbox.id, position=0)
    seq = await make_sequence(session, campaign.id, subject="Hi {{name}}")
    account = GmailAccount(inbox_id=inbox.id, google_email="primary@example.com",
                           access_token="fake", refresh_token="fake")
    session.add_all([account, GmailAccount(inbox_id=other.id,
                    google_email=inbox.email, access_token="other", refresh_token="other")])
    await session.flush()
    captured = {}

    def fake_send(**kwargs):
        captured.update(kwargs)
        return sender.SendResult(message_id="mock-test", thread_id="mock-thread")

    monkeypatch.setattr(sender, "send_email", fake_send)
    app = FastAPI()
    app.include_router(router)

    async def local_db():
        yield session

    app.dependency_overrides[get_db] = local_db
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False),
                           base_url="http://test") as client:
        response = await client.post(f"/api/campaigns/{campaign.id}/send-test", json={
            "sequence_id": seq.id, "to_email": "recipient@example.com",
        })
    assert response.status_code == 200, response.text
    assert response.json() == {"ok": True, "message_id": "mock-test"}
    assert captured["gmail_account"] is account
    assert captured["from_email"] == inbox.email
    assert captured["to_email"] == "recipient@example.com"
    assert captured["subject"] == "[TEST] Hi Test User"


@pytest.mark.asyncio
async def test_scheduler_keeps_allowed_today_before_window():
    """Deterministic guard for the Sunday/current-day window decision."""
    today = datetime(2026, 10, 4).date()  # Sunday
    result = await _next_available_send_time_today(
        AsyncMock(), 1, today, "14:04", "14:08", 1,
        datetime(2026, 10, 4, 13, 55), {("_preseeded",): True},
    )
    assert result == datetime(2026, 10, 4, 14, 4)


@pytest.mark.asyncio
async def test_recalculate_campaign_queue_post_handles_campaign_without_leads(session):
    from app.routers import campaigns as campaigns_router

    campaign = await make_campaign(session)
    result = await campaigns_router.recalculate_campaign_queue(campaign.id, db=session)
    assert result == {"ok": True, "campaign_id": campaign.id, "leads": 0, "slots": 0}


@pytest.mark.asyncio
async def test_recalculate_campaign_queue_post_rebuilds_active_lead(session):
    from app.routers import campaigns as campaigns_router

    campaign = await make_campaign(
        session,
        sending_days=[0, 1, 2, 3, 4, 5, 6],
        sending_hours_start="00:00",
        sending_hours_end="23:59",
    )
    inbox = await make_inbox(session)
    await make_campaign_inbox(session, campaign.id, inbox.id)
    await make_sequence(session, campaign.id)
    lead = await make_lead(session)
    await make_campaign_lead(session, campaign.id, lead.id)

    result = await campaigns_router.recalculate_campaign_queue(campaign.id, db=session)

    assert result["ok"] is True
    assert result["campaign_id"] == campaign.id
    assert result["leads"] == 1
    assert result["slots"] == 1

@pytest.mark.asyncio
@pytest.mark.parametrize('hour,minute,dates,expected', [
    (18,38,['2026-10-04'],datetime(2026,10,4,22,39)),
    (18,40,['2026-10-04'],datetime(2026,10,4,22,41)),
    (18,43,['2026-10-04'],None),
    (18,43,['2026-10-05'],datetime(2026,10,5,22,39)),
    (18,43,['2026-10-03'],None),
])
async def test_explicit_date_queue_windows(session, monkeypatch, hour, minute, dates, expected):
    from app import queue_logic
    from app.models import QueueSlot
    from app.routers.campaigns import recalculate_campaign_queue
    campaign = await make_campaign(session, sending_days=dates,
        sending_hours_start='18:39', sending_hours_end='18:42')
    campaign.timezone = 'America/New_York'
    inbox = await make_inbox(session)
    await make_campaign_inbox(session, campaign.id, inbox.id)
    await make_sequence(session, campaign.id)
    lead = await make_lead(session)
    await make_campaign_lead(session, campaign.id, lead.id)
    monkeypatch.setattr(queue_logic, '_campaign_now', lambda _: datetime(2026,10,4,hour,minute))
    monkeypatch.setattr(queue_logic.time_provider, 'today', lambda: datetime(2026,10,4).date())
    monkeypatch.setattr(queue_logic, '_apply_jitter', lambda dt, _: dt)
    result = await recalculate_campaign_queue(campaign.id, db=session)
    slots = (await session.execute(select(QueueSlot))).scalars().all()
    assert [s.scheduled_date for s in slots] == ([expected] if expected else [])
    if expected is None:
        assert result['reason']
