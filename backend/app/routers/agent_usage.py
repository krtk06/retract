"""Agent-only accounting: session ownership, usage intake, and budget checks.

The eve agent runs as a separate service and cannot present a browser session,
so these routes authenticate with the shared ``X-Agent-Token`` service secret
(``deps.get_agent_service``). None of them accept a cookie: usage and budget data
are account-scoped, and a browser-facing variant would let any signed-in user
read or write another account's ledger.

The agent posts one usage event per completed model call. The event id is the
primary key, so a retried report is a no-op rather than a second charge.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.agent_usage import budget_snapshot, record_usage, upsert_session
from app.config import get_settings
from app.db import get_db
from app.deps import get_agent_service
from app.models import AgentSession, User
from app.schemas import AgentBudgetOut, AgentSessionIn, AgentSessionOut, AgentUsageIn, AgentUsageOut

router = APIRouter(
    prefix="/agent",
    tags=["agent"],
    dependencies=[Depends(get_agent_service)],
)


def _user_or_404(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.post("/sessions", response_model=AgentSessionOut)
def map_session(payload: AgentSessionIn, db: Session = Depends(get_db)) -> AgentSessionOut:
    """Record which account an eve session (root or child) spends for."""
    _user_or_404(db, payload.user_id)
    upsert_session(db, session_id=payload.session_id, user_id=payload.user_id)
    db.commit()
    return AgentSessionOut(session_id=payload.session_id, user_id=payload.user_id)


@router.post("/usage", response_model=AgentUsageOut)
def report_usage(payload: AgentUsageIn, db: Session = Depends(get_db)) -> AgentUsageOut:
    """Add one completed model call to its account's monthly ledger."""
    session = db.get(AgentSession, payload.session_id)
    if session is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="Unknown agent session; map it before reporting usage",
        )
    recorded = record_usage(
        db,
        idempotency_key=payload.idempotency_key,
        user_id=session.user_id,
        session_id=payload.session_id,
        model=payload.model,
        input_tokens=payload.input_tokens,
        output_tokens=payload.output_tokens,
        cost_usd=payload.cost_usd,
    )
    db.commit()
    return AgentUsageOut(recorded=recorded)


@router.get("/budget", response_model=AgentBudgetOut)
def get_budget(user_id: int = Query(ge=1), db: Session = Depends(get_db)) -> AgentBudgetOut:
    """The remaining monthly budget the agent checks before dispatching a turn."""
    user = _user_or_404(db, user_id)
    snapshot = budget_snapshot(db, user, get_settings())
    return AgentBudgetOut.model_validate(snapshot)
