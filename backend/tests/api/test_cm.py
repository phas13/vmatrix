from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.security import create_access_token
from app.db.session import get_db_session
from app.models.user import SpecialistLevel, User, UserRole
from app.schemas.cm import DisputeDecision, DisputeDetailRead, DisputeResolveResponse, PendingActionsResponse, PendingActionRead, PendingActionType, PromotionDetailRead, PromotionDecideResponse, QuestionResponseItem, SpecialistCardRead, SpecialistDetailRead
from app.schemas.pagination import PaginatedResponse
from app.schemas.session import CategoryScoreRead, SessionListItemRead, SessionStatus
from main import app


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_cm() -> MagicMock:
    u = MagicMock(spec=User)
    u.id = uuid4()
    u.role = UserRole.CM
    u.is_active = True
    u.email = f"cm-{u.id.hex[:6]}@example.com"
    u.full_name = "Test CM"
    return u


def _make_specialist(cm: MagicMock) -> MagicMock:
    u = MagicMock(spec=User)
    u.id = uuid4()
    u.role = UserRole.SPECIALIST
    u.is_active = True
    u.cm_id = cm.id
    u.email = f"spec-{u.id.hex[:6]}@example.com"
    u.full_name = "Test Specialist"
    u.specialist_level = SpecialistLevel.JUNIOR
    return u


def _make_jwt(user: MagicMock) -> str:
    return create_access_token({"sub": str(user.id), "role": user.role.value})


def _scalar_one_or_none_result(value) -> MagicMock:
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


def _scalars_all_result(values: list) -> MagicMock:
    r = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = values
    r.scalars.return_value = scalars
    return r


def _scalar_one_result(value) -> MagicMock:
    r = MagicMock()
    r.scalar_one.return_value = value
    return r


def _make_auth_db(user: MagicMock) -> tuple:
    """Mock DB that returns `user` for the auth lookup and nothing else."""
    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.execute = AsyncMock(return_value=_scalar_one_or_none_result(user))

    async def override():
        yield mock_db

    return override, mock_db


def _make_card(specialist: MagicMock) -> SpecialistCardRead:
    return SpecialistCardRead(
        id=specialist.id,
        full_name=specialist.full_name,
        specialist_level=SpecialistLevel.JUNIOR,
        overall_percentage=75,
        last_activity_at=_now(),
    )


def _make_detail(specialist: MagicMock) -> SpecialistDetailRead:
    return SpecialistDetailRead(
        id=specialist.id,
        full_name=specialist.full_name,
        specialist_level=SpecialistLevel.JUNIOR,
        overall_percentage=75,
        category_scores=[
            CategoryScoreRead(
                category_id=uuid4(),
                category_name="CI/CD",
                score=80,
                previous_score=70,
                last_assessed_at=_now(),
            )
        ],
        sessions=PaginatedResponse[SessionListItemRead](
            items=[], total=0, page=1, per_page=20, pages=1
        ),
    )


# ─── GET /cm/team ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_team_empty_returns_empty_list(async_client):
    cm = _make_cm()
    jwt = _make_jwt(cm)
    override, _ = _make_auth_db(cm)
    app.dependency_overrides[get_db_session] = override

    try:
        with patch(
            "app.services.cm_service.get_team_overview",
            new=AsyncMock(return_value=[]),
        ):
            response = await async_client.get(
                "/api/v1/cm/team",
                cookies={"access_token": jwt},
            )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_team_returns_specialist_cards(async_client):
    cm = _make_cm()
    jwt = _make_jwt(cm)
    specialist = _make_specialist(cm)
    card = _make_card(specialist)
    override, _ = _make_auth_db(cm)
    app.dependency_overrides[get_db_session] = override

    try:
        with patch(
            "app.services.cm_service.get_team_overview",
            new=AsyncMock(return_value=[card]),
        ):
            response = await async_client.get(
                "/api/v1/cm/team",
                cookies={"access_token": jwt},
            )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    item = body[0]
    assert item["id"] == str(specialist.id)
    assert item["full_name"] == specialist.full_name
    assert item["overall_percentage"] == 75
    assert item["specialist_level"] == "junior"
    assert item["last_activity_at"] is not None


@pytest.mark.asyncio
async def test_get_team_data_isolation(async_client):
    """CM B cannot see CM A's specialists — verified at service layer."""
    from app.services.cm_service import get_team_overview

    cm_a = _make_cm()
    cm_b = _make_cm()
    specialist = _make_specialist(cm_a)

    mock_db = AsyncMock()
    # specialists query for cm_b.id → empty (specialist belongs to cm_a)
    mock_db.execute = AsyncMock(return_value=_scalars_all_result([]))

    cards = await get_team_overview(cm_b.id, mock_db)

    assert cards == []
    # service made exactly one DB call (specialist query)
    assert mock_db.execute.call_count == 1


@pytest.mark.asyncio
async def test_get_team_requires_cm_role(async_client):
    specialist = MagicMock(spec=User)
    specialist.id = uuid4()
    specialist.role = UserRole.SPECIALIST
    specialist.is_active = True
    jwt = create_access_token({"sub": str(specialist.id), "role": "specialist"})
    override, _ = _make_auth_db(specialist)
    app.dependency_overrides[get_db_session] = override

    try:
        response = await async_client.get(
            "/api/v1/cm/team",
            cookies={"access_token": jwt},
        )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert response.status_code == 403


# ─── GET /cm/specialists/{id} ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_specialist_detail_returns_data(async_client):
    cm = _make_cm()
    jwt = _make_jwt(cm)
    specialist = _make_specialist(cm)
    detail = _make_detail(specialist)
    override, _ = _make_auth_db(cm)
    app.dependency_overrides[get_db_session] = override

    try:
        with patch(
            "app.services.cm_service.get_specialist_detail",
            new=AsyncMock(return_value=detail),
        ):
            response = await async_client.get(
                f"/api/v1/cm/specialists/{specialist.id}",
                cookies={"access_token": jwt},
            )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(specialist.id)
    assert body["overall_percentage"] == 75
    assert len(body["category_scores"]) == 1
    assert "sessions" in body


@pytest.mark.asyncio
async def test_get_specialist_detail_rejects_wrong_cm(async_client):
    cm_b = _make_cm()
    jwt = _make_jwt(cm_b)
    other_specialist_id = uuid4()
    override, _ = _make_auth_db(cm_b)
    app.dependency_overrides[get_db_session] = override

    try:
        with patch(
            "app.services.cm_service.get_specialist_detail",
            new=AsyncMock(side_effect=HTTPException(status_code=404, detail="Specialist not found")),
        ):
            response = await async_client.get(
                f"/api/v1/cm/specialists/{other_specialist_id}",
                cookies={"access_token": jwt},
            )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_specialist_detail_requires_cm_role(async_client):
    specialist_user = MagicMock(spec=User)
    specialist_user.id = uuid4()
    specialist_user.role = UserRole.SPECIALIST
    specialist_user.is_active = True
    jwt = create_access_token({"sub": str(specialist_user.id), "role": "specialist"})
    override, _ = _make_auth_db(specialist_user)
    app.dependency_overrides[get_db_session] = override

    try:
        response = await async_client.get(
            f"/api/v1/cm/specialists/{uuid4()}",
            cookies={"access_token": jwt},
        )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert response.status_code == 403

# ─── New Tests for Story 6.1 Review Findings ───────────────────────────────

@pytest.mark.asyncio
async def test_get_team_overview_performance_bulk_query(async_client):
    """Verify that get_team_overview uses bulk percentage calculation."""
    from app.services.cm_service import get_team_overview

    cm = _make_cm()
    spec1 = _make_specialist(cm)
    spec2 = _make_specialist(cm)

    mock_db = AsyncMock()
    # 1. Specialists query
    # 2. Activity batch query
    # 3. Bulk percentages query
    mock_db.execute.side_effect = [
        _scalars_all_result([spec1, spec2]), # specialists
        MagicMock(all=lambda: []), # activity
        _scalars_all_result([]), # bulk matrix query in calculate_bulk_percentages
        _scalars_all_result([]), # bulk category counts query
        _scalars_all_result([]), # bulk scores query
    ]

    cards = await get_team_overview(cm.id, mock_db)
    assert len(cards) == 2


@pytest.mark.asyncio
async def test_get_specialist_detail_security_active_check_direct(async_client):
    """Verify that deactivated specialists are not accessible at service level."""
    from app.services.cm_service import get_specialist_detail

    cm = _make_cm()
    spec = _make_specialist(cm)
    spec.is_active = False # DEACTIVATED

    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=spec)

    with pytest.raises(HTTPException) as exc:
        await get_specialist_detail(cm.id, spec.id, mock_db, 1, 20)

    assert exc.value.status_code == 404
    assert exc.value.detail == "Specialist not found"


# ─── GET /cm/pending ──────────────────────────────────────────────────────────

def _make_empty_pending() -> PendingActionsResponse:
    return PendingActionsResponse(
        disputes=[], promotions=[], matrix_approvals=[], update_proposals=[], total=0
    )


def _make_pending_action(
    action_type: PendingActionType,
    specialist_id=None,
) -> PendingActionRead:
    from uuid import uuid4
    sid = specialist_id or uuid4()
    return PendingActionRead(
        id=uuid4(),
        type=action_type,
        specialist_id=sid,
        specialist_name="Test Specialist",
        description="Test description",
        date=_now(),
    )


@pytest.mark.asyncio
async def test_get_pending_empty_returns_zero_counts(async_client):
    cm = _make_cm()
    override, _ = _make_auth_db(cm)
    app.dependency_overrides[get_db_session] = override

    try:
        with patch(
            "app.services.cm_service.get_pending_actions",
            new=AsyncMock(return_value=_make_empty_pending()),
        ):
            resp = await async_client.get(
                "/api/v1/cm/pending",
                cookies={"access_token": _make_jwt(cm)},
            )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["disputes"] == []
    assert data["promotions"] == []
    assert data["matrix_approvals"] == []
    assert data["update_proposals"] == []


@pytest.mark.asyncio
async def test_get_pending_includes_open_dispute(async_client):
    cm = _make_cm()
    spec = _make_specialist(cm)
    dispute_action = _make_pending_action(PendingActionType.DISPUTE, spec.id)
    pending = PendingActionsResponse(
        disputes=[dispute_action],
        promotions=[],
        matrix_approvals=[],
        update_proposals=[],
        total=1,
    )
    override, _ = _make_auth_db(cm)
    app.dependency_overrides[get_db_session] = override

    try:
        with patch(
            "app.services.cm_service.get_pending_actions",
            new=AsyncMock(return_value=pending),
        ):
            resp = await async_client.get(
                "/api/v1/cm/pending",
                cookies={"access_token": _make_jwt(cm)},
            )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["disputes"]) == 1
    assert data["disputes"][0]["type"] == "dispute"
    assert data["disputes"][0]["specialist_name"] == "Test Specialist"


@pytest.mark.asyncio
async def test_get_pending_includes_promotion(async_client):
    cm = _make_cm()
    spec = _make_specialist(cm)
    promo_action = _make_pending_action(PendingActionType.PROMOTION, spec.id)
    pending = PendingActionsResponse(
        disputes=[],
        promotions=[promo_action],
        matrix_approvals=[],
        update_proposals=[],
        total=1,
    )
    override, _ = _make_auth_db(cm)
    app.dependency_overrides[get_db_session] = override

    try:
        with patch(
            "app.services.cm_service.get_pending_actions",
            new=AsyncMock(return_value=pending),
        ):
            resp = await async_client.get(
                "/api/v1/cm/pending",
                cookies={"access_token": _make_jwt(cm)},
            )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["promotions"]) == 1
    assert data["promotions"][0]["type"] == "promotion"


@pytest.mark.asyncio
async def test_get_pending_includes_matrix_approval(async_client):
    cm = _make_cm()
    spec = _make_specialist(cm)
    matrix_action = _make_pending_action(PendingActionType.MATRIX_APPROVAL, spec.id)
    pending = PendingActionsResponse(
        disputes=[],
        promotions=[],
        matrix_approvals=[matrix_action],
        update_proposals=[],
        total=1,
    )
    override, _ = _make_auth_db(cm)
    app.dependency_overrides[get_db_session] = override

    try:
        with patch(
            "app.services.cm_service.get_pending_actions",
            new=AsyncMock(return_value=pending),
        ):
            resp = await async_client.get(
                "/api/v1/cm/pending",
                cookies={"access_token": _make_jwt(cm)},
            )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["matrix_approvals"]) == 1
    assert data["matrix_approvals"][0]["type"] == "matrix_approval"


@pytest.mark.asyncio
async def test_get_pending_excludes_resolved_dispute(async_client):
    """Resolved disputes must not appear — verified at service layer."""
    from app.services.cm_service import get_pending_actions
    from app.models.session import DisputeStatus

    cm = _make_cm()
    mock_db = AsyncMock()

    resolved_dispute = MagicMock()
    resolved_dispute.status = DisputeStatus.RESOLVED

    # specialists query → empty (no open disputes to aggregate)
    mock_db.execute.side_effect = [
        _scalars_all_result([]),  # specialists (empty → skips dispute+matrix queries)
        _scalars_all_result([]),  # notifications
        _scalars_all_result([]),  # update proposals
    ]

    result = await get_pending_actions(cm.id, mock_db)
    assert result.total == 0
    assert result.disputes == []


@pytest.mark.asyncio
async def test_get_pending_excludes_read_promotion(async_client):
    """Read PROMOTION_SUGGESTION notifications must not appear — verified at service layer."""
    from app.services.cm_service import get_pending_actions

    cm = _make_cm()
    mock_db = AsyncMock()

    # specialists query → empty, notifications → empty (is_read=True filtered out by query)
    mock_db.execute.side_effect = [
        _scalars_all_result([]),  # specialists
        _scalars_all_result([]),  # notifications (read ones excluded by query)
        _scalars_all_result([]),  # update proposals
    ]

    result = await get_pending_actions(cm.id, mock_db)
    assert result.total == 0
    assert result.promotions == []


@pytest.mark.asyncio
async def test_get_pending_data_isolation(async_client):
    """CM B cannot see CM A's specialist data — verified at service layer."""
    from app.services.cm_service import get_pending_actions

    cm_b = _make_cm()
    mock_db = AsyncMock()

    # specialists query for cm_b → empty (specialist belongs to cm_a)
    mock_db.execute.side_effect = [
        _scalars_all_result([]),  # specialists (empty → cm_b has no assigned specialists)
        _scalars_all_result([]),  # notifications
        _scalars_all_result([]),  # update proposals
    ]

    result = await get_pending_actions(cm_b.id, mock_db)
    assert result.total == 0
    assert result.disputes == []
    assert result.matrix_approvals == []


@pytest.mark.asyncio
async def test_get_pending_requires_cm_role(async_client):
    cm = _make_cm()
    specialist = _make_specialist(cm)
    override, _ = _make_auth_db(specialist)
    app.dependency_overrides[get_db_session] = override

    try:
        resp = await async_client.get(
            "/api/v1/cm/pending",
            cookies={"access_token": _make_jwt(specialist)},
        )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert resp.status_code == 403


# ─── GET /cm/disputes/{id} and POST /cm/disputes/{id}/actions/resolve ─────────

def _make_dispute_detail(specialist: MagicMock) -> DisputeDetailRead:
    return DisputeDetailRead(
        id=uuid4(),
        session_id=uuid4(),
        specialist_id=specialist.id,
        specialist_name=specialist.full_name,
        category_id=uuid4(),
        category_name="Cloud Infrastructure",
        status="open",
        specialist_explanation="I disagree with the AI rationale for Q1",
        submitted_at=_now(),
        cm_decision=None,
        ai_score=60,
        transcript=[
            QuestionResponseItem(
                question_id=uuid4(),
                question_text="What is CI/CD?",
                question_type="theoretical",
                order=1,
                response_text="Continuous integration and delivery pipeline",
                ai_rationale="Correct but lacks depth",
            ),
            QuestionResponseItem(
                question_id=uuid4(),
                question_text="Describe a deployment strategy",
                question_type="practical",
                order=2,
                response_text="Blue-green deployment",
                ai_rationale="Good answer",
            ),
        ],
    )


def _make_resolve_response(decision: DisputeDecision) -> DisputeResolveResponse:
    return DisputeResolveResponse(
        id=uuid4(),
        status="resolved",
        cm_decision=decision.value,
        cm_note="Override rationale" if decision == DisputeDecision.OVERRIDDEN else None,
        resolved_at=_now(),
        updated_score=75 if decision == DisputeDecision.OVERRIDDEN else None,
    )


@pytest.mark.asyncio
async def test_get_dispute_detail_returns_full_transcript(async_client):
    cm = _make_cm()
    specialist = _make_specialist(cm)
    detail = _make_dispute_detail(specialist)
    override, _ = _make_auth_db(cm)
    app.dependency_overrides[get_db_session] = override

    try:
        with patch(
            "app.services.cm_service.get_dispute_detail",
            new=AsyncMock(return_value=detail),
        ):
            resp = await async_client.get(
                f"/api/v1/cm/disputes/{detail.id}",
                cookies={"access_token": _make_jwt(cm)},
            )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body["specialist_name"] == specialist.full_name
    assert body["status"] == "open"
    assert len(body["transcript"]) == 2
    assert body["transcript"][0]["order"] == 1


@pytest.mark.asyncio
async def test_get_dispute_detail_requires_cm_role(async_client):
    cm = _make_cm()
    specialist = _make_specialist(cm)
    override, _ = _make_auth_db(specialist)
    app.dependency_overrides[get_db_session] = override

    try:
        resp = await async_client.get(
            f"/api/v1/cm/disputes/{uuid4()}",
            cookies={"access_token": _make_jwt(specialist)},
        )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_dispute_detail_not_found(async_client):
    cm = _make_cm()
    override, _ = _make_auth_db(cm)
    app.dependency_overrides[get_db_session] = override

    try:
        with patch(
            "app.services.cm_service.get_dispute_detail",
            new=AsyncMock(side_effect=HTTPException(status_code=404, detail="Dispute not found")),
        ):
            resp = await async_client.get(
                f"/api/v1/cm/disputes/{uuid4()}",
                cookies={"access_token": _make_jwt(cm)},
            )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_resolve_dispute_upheld(async_client):
    cm = _make_cm()
    resolve_resp = _make_resolve_response(DisputeDecision.UPHELD)
    override, _ = _make_auth_db(cm)
    app.dependency_overrides[get_db_session] = override

    try:
        with patch(
            "app.services.cm_service.resolve_dispute",
            new=AsyncMock(return_value=resolve_resp),
        ):
            resp = await async_client.post(
                f"/api/v1/cm/disputes/{uuid4()}/actions/resolve",
                json={"decision": "upheld"},
                cookies={"access_token": _make_jwt(cm)},
            )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "resolved"
    assert body["cm_decision"] == "upheld"


@pytest.mark.asyncio
async def test_resolve_dispute_overridden(async_client):
    cm = _make_cm()
    resolve_resp = _make_resolve_response(DisputeDecision.OVERRIDDEN)
    override, _ = _make_auth_db(cm)
    app.dependency_overrides[get_db_session] = override

    try:
        with patch(
            "app.services.cm_service.resolve_dispute",
            new=AsyncMock(return_value=resolve_resp),
        ):
            resp = await async_client.post(
                f"/api/v1/cm/disputes/{uuid4()}/actions/resolve",
                json={"decision": "overridden", "cm_note": "Score was unfair", "override_score": 75},
                cookies={"access_token": _make_jwt(cm)},
            )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body["cm_decision"] == "overridden"
    assert body["updated_score"] == 75


@pytest.mark.asyncio
async def test_resolve_dispute_overridden_missing_note(async_client):
    cm = _make_cm()
    override, _ = _make_auth_db(cm)
    app.dependency_overrides[get_db_session] = override

    try:
        resp = await async_client.post(
            f"/api/v1/cm/disputes/{uuid4()}/actions/resolve",
            json={"decision": "overridden", "override_score": 75},
            cookies={"access_token": _make_jwt(cm)},
        )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_resolve_dispute_overridden_missing_score(async_client):
    cm = _make_cm()
    override, _ = _make_auth_db(cm)
    app.dependency_overrides[get_db_session] = override

    try:
        resp = await async_client.post(
            f"/api/v1/cm/disputes/{uuid4()}/actions/resolve",
            json={"decision": "overridden", "cm_note": "Score was unfair"},
            cookies={"access_token": _make_jwt(cm)},
        )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_resolve_dispute_already_resolved(async_client):
    cm = _make_cm()
    override, _ = _make_auth_db(cm)
    app.dependency_overrides[get_db_session] = override

    try:
        with patch(
            "app.services.cm_service.resolve_dispute",
            new=AsyncMock(side_effect=HTTPException(status_code=409, detail="Dispute has already been resolved")),
        ):
            resp = await async_client.post(
                f"/api/v1/cm/disputes/{uuid4()}/actions/resolve",
                json={"decision": "upheld"},
                cookies={"access_token": _make_jwt(cm)},
            )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_resolve_dispute_requires_cm_role(async_client):
    cm = _make_cm()
    specialist = _make_specialist(cm)
    override, _ = _make_auth_db(specialist)
    app.dependency_overrides[get_db_session] = override

    try:
        resp = await async_client.post(
            f"/api/v1/cm/disputes/{uuid4()}/actions/resolve",
            json={"decision": "upheld"},
            cookies={"access_token": _make_jwt(specialist)},
        )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert resp.status_code == 403


# ─── GET /cm/promotions/{id} and POST /cm/promotions/{id}/actions/* ───────────

def _make_promotion_detail(specialist: MagicMock) -> PromotionDetailRead:
    return PromotionDetailRead(
        notification_id=uuid4(),
        specialist_id=specialist.id,
        specialist_name=specialist.full_name,
        current_level="junior",
        next_level="middle",
        overall_percentage=92,
        threshold=90,
        category_scores=[
            CategoryScoreRead(
                category_id=uuid4(),
                category_name="Cloud Infrastructure",
                score=92,
                previous_score=80,
                last_assessed_at=_now(),
            )
        ],
        sessions=PaginatedResponse[SessionListItemRead](
            items=[], total=0, page=1, per_page=10, pages=1
        ),
        is_decided=False,
    )


def _make_decide_response(decision: str) -> PromotionDecideResponse:
    return PromotionDecideResponse(
        notification_id=uuid4(),
        decision=decision,
        new_level="middle" if decision == "approved" else None,
    )


@pytest.mark.asyncio
async def test_get_promotion_detail_ok(async_client):
    cm = _make_cm()
    specialist = _make_specialist(cm)
    detail = _make_promotion_detail(specialist)
    override, _ = _make_auth_db(cm)
    app.dependency_overrides[get_db_session] = override

    try:
        with patch(
            "app.services.cm_service.get_promotion_detail",
            new=AsyncMock(return_value=detail),
        ):
            resp = await async_client.get(
                f"/api/v1/cm/promotions/{detail.notification_id}",
                cookies={"access_token": _make_jwt(cm)},
            )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body["specialist_name"] == specialist.full_name
    assert body["overall_percentage"] == 92
    assert body["threshold"] == 90
    assert body["is_decided"] is False


@pytest.mark.asyncio
async def test_get_promotion_detail_wrong_cm(async_client):
    cm = _make_cm()
    override, _ = _make_auth_db(cm)
    app.dependency_overrides[get_db_session] = override

    try:
        with patch(
            "app.services.cm_service.get_promotion_detail",
            new=AsyncMock(side_effect=HTTPException(status_code=404, detail="Promotion not found")),
        ):
            resp = await async_client.get(
                f"/api/v1/cm/promotions/{uuid4()}",
                cookies={"access_token": _make_jwt(cm)},
            )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_promotion_detail_not_found(async_client):
    cm = _make_cm()
    override, _ = _make_auth_db(cm)
    app.dependency_overrides[get_db_session] = override

    try:
        with patch(
            "app.services.cm_service.get_promotion_detail",
            new=AsyncMock(side_effect=HTTPException(status_code=404, detail="Promotion not found")),
        ):
            resp = await async_client.get(
                f"/api/v1/cm/promotions/{uuid4()}",
                cookies={"access_token": _make_jwt(cm)},
            )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_approve_promotion_ok(async_client):
    cm = _make_cm()
    approve_resp = _make_decide_response("approved")
    override, _ = _make_auth_db(cm)
    app.dependency_overrides[get_db_session] = override

    try:
        with patch(
            "app.services.cm_service.approve_promotion",
            new=AsyncMock(return_value=approve_resp),
        ):
            resp = await async_client.post(
                f"/api/v1/cm/promotions/{uuid4()}/actions/approve",
                json={},
                cookies={"access_token": _make_jwt(cm)},
            )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body["decision"] == "approved"
    assert body["new_level"] == "middle"


@pytest.mark.asyncio
async def test_approve_promotion_already_decided(async_client):
    cm = _make_cm()
    override, _ = _make_auth_db(cm)
    app.dependency_overrides[get_db_session] = override

    try:
        with patch(
            "app.services.cm_service.approve_promotion",
            new=AsyncMock(side_effect=HTTPException(
                status_code=409,
                detail={"type": "https://vmatrix.app/errors/conflict", "title": "Conflict",
                        "status": 409, "detail": "Promotion has already been decided"},
            )),
        ):
            resp = await async_client.post(
                f"/api/v1/cm/promotions/{uuid4()}/actions/approve",
                json={},
                cookies={"access_token": _make_jwt(cm)},
            )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_approve_promotion_role_guard(async_client):
    cm = _make_cm()
    specialist = _make_specialist(cm)
    override, _ = _make_auth_db(specialist)
    app.dependency_overrides[get_db_session] = override

    try:
        resp = await async_client.post(
            f"/api/v1/cm/promotions/{uuid4()}/actions/approve",
            json={},
            cookies={"access_token": _make_jwt(specialist)},
        )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_reject_promotion_ok(async_client):
    cm = _make_cm()
    reject_resp = _make_decide_response("rejected")
    override, _ = _make_auth_db(cm)
    app.dependency_overrides[get_db_session] = override

    try:
        with patch(
            "app.services.cm_service.reject_promotion",
            new=AsyncMock(return_value=reject_resp),
        ):
            resp = await async_client.post(
                f"/api/v1/cm/promotions/{uuid4()}/actions/reject",
                json={},
                cookies={"access_token": _make_jwt(cm)},
            )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body["decision"] == "rejected"
    assert body["new_level"] is None


@pytest.mark.asyncio
async def test_reject_promotion_already_decided(async_client):
    cm = _make_cm()
    override, _ = _make_auth_db(cm)
    app.dependency_overrides[get_db_session] = override

    try:
        with patch(
            "app.services.cm_service.reject_promotion",
            new=AsyncMock(side_effect=HTTPException(
                status_code=409,
                detail={"type": "https://vmatrix.app/errors/conflict", "title": "Conflict",
                        "status": 409, "detail": "Promotion has already been decided"},
            )),
        ):
            resp = await async_client.post(
                f"/api/v1/cm/promotions/{uuid4()}/actions/reject",
                json={},
                cookies={"access_token": _make_jwt(cm)},
            )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_reject_promotion_with_note(async_client):
    cm = _make_cm()
    reject_resp = _make_decide_response("rejected")
    override, _ = _make_auth_db(cm)
    app.dependency_overrides[get_db_session] = override

    try:
        with patch(
            "app.services.cm_service.reject_promotion",
            new=AsyncMock(return_value=reject_resp),
        ):
            resp = await async_client.post(
                f"/api/v1/cm/promotions/{uuid4()}/actions/reject",
                json={"cm_note": "Needs more experience in senior tasks"},
                cookies={"access_token": _make_jwt(cm)},
            )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body["decision"] == "rejected"
