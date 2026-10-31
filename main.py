import asyncio
import hashlib
import json
import os
import uuid
from typing import Any
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agent import analyze_invoice_batch
from database import ProcessedMessage, Task, get_db, init_db
from schemas import ActionResultsData, InvoiceBatchData, SendMessageRequest


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="A2A Invoice Agent",
    description="AI-powered invoice decision agent",
    version="1.0.0",
    lifespan=lifespan,
)

BASE_URL = os.getenv(
    "A2A_BASE_URL",
    "http://127.0.0.1:8000/a2a",
)
A2A_JSON = "application/a2a+json"
MAX_RESPONSE_SIZE = 512 * 1024


def a2a_response(content: dict[str, Any]) -> JSONResponse:
    response = JSONResponse(
        content=content,
        media_type=A2A_JSON,
    )

    if len(response.body) > MAX_RESPONSE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Response exceeds 512 KiB limit",
        )

    return response
CLAIM_MEDIA_TYPE = "application/vnd.ga5.invoice-claim-batch+json"
RESULTS_MEDIA_TYPE = "application/vnd.ga5.invoice-action-results+json"
PROPOSALS_MEDIA_TYPE = "application/vnd.ga5.invoice-action-proposals+json"
RECEIPTS_MEDIA_TYPE = "application/vnd.ga5.invoice-action-receipts+json"

# A single-worker deployment is recommended. This lock prevents two equivalent
# initial requests in this process from calling the model at the same time.
_initial_request_lock = asyncio.Lock()


def authenticate_request(
    authorization: str | None,
    a2a_version: str | None,
) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")

    token = authorization[len("Bearer "):]
    if not token or not token.strip():
        raise HTTPException(status_code=401, detail="Authentication required")

    if a2a_version != "1.0":
        raise HTTPException(status_code=400, detail="Unsupported A2A version")

    # Every Bearer token is a separate user. Store a digest as the owner
    # identifier; never store the raw bearer token.
    return hashlib.sha256(token.strip().encode("utf-8")).hexdigest()


def validate_content_type(request: Request) -> None:
    content_type = request.headers.get("content-type", "")
    media_type = content_type.split(";", 1)[0].strip().lower()

    if media_type != A2A_JSON:
        raise HTTPException(status_code=415, detail="Unsupported media type")


def generate_message_hash(message: dict[str, Any]) -> str:
    """Hash the message only; configuration is deliberately excluded."""
    canonical_json = json.dumps(
        message,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def task_to_dict(task: Task) -> dict[str, Any]:
    return {
        "id": task.id,
        "contextId": task.context_id,
        "kind": "task",
        "status": {"state": task.state},
        "artifacts": task.artifacts or [],
        "history": task.history or [],
    }


def task_envelope(task: Task) -> dict[str, Any]:
    return {"task": task_to_dict(task)}


def find_proposal_data(task: Task) -> dict[str, Any] | None:
    for artifact in task.artifacts or []:
        for part in artifact.get("parts", []):
            if part.get("mediaType") == PROPOSALS_MEDIA_TYPE:
                return part.get("data")
    return None


def get_processed_message(
    db: Session,
    principal: str,
    message_id: str,
) -> ProcessedMessage | None:
    return db.get(
        ProcessedMessage,
        {"principal": principal, "message_id": message_id},
    )


def replay_or_conflict(
    existing: ProcessedMessage | None,
    message_hash: str,
) -> JSONResponse | None:
    if existing is None:
        return None

    if existing.request_hash != message_hash:
        raise HTTPException(status_code=409, detail="IDEMPOTENCY_CONFLICT")

    return a2a_response(existing.response_data)

@app.get("/")
def home() -> dict[str, str]:
    return {"message": "A2A Invoice Agent is running"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/.well-known/agent-card.json")
def agent_card() -> JSONResponse:
    card = {
        "name": "Invoice Action Agent",
        "description": (
            "Analyzes invoice packages, proposes safe business actions, "
            "and records accepted execution receipts."
        ),
        "version": "1.0.0",
        "capabilities": {},
        "supportedInterfaces": [
            {
                "url": BASE_URL,
                "protocolBinding": "HTTP+JSON",
                "protocolVersion": "1.0",
            }
        ],
        "defaultInputModes": [CLAIM_MEDIA_TYPE],
        "defaultOutputModes": [PROPOSALS_MEDIA_TYPE, RECEIPTS_MEDIA_TYPE],
        "skills": [
            {
                "id": "invoice_action_agent",
                "name": "Invoice Action Agent",
                "description": (
                    "Evaluates invoices and proposes evidence-based "
                    "business actions."
                ),
                "tags": ["invoice", "payments", "approval", "reconciliation"],
            }
        ],
    }
    return JSONResponse(content=card, media_type=A2A_JSON)


@app.get("/a2a/dev-check")
def protected_test(
    authorization: str | None = Header(default=None),
    a2a_version: str | None = Header(default=None, alias="A2A-Version"),
) -> dict[str, Any]:
    authenticate_request(authorization, a2a_version)
    return {"authenticated": True, "protocol_version": "1.0"}


@app.post("/a2a/message:send")
async def send_message(
    request: Request,
    payload: SendMessageRequest,
    authorization: str | None = Header(default=None),
    a2a_version: str | None = Header(default=None, alias="A2A-Version"),
    db: Session = Depends(get_db),
) -> JSONResponse:
    principal = authenticate_request(authorization, a2a_version)
    validate_content_type(request)

    raw_body = await request.json()
    raw_message = raw_body.get("message")
    if not isinstance(raw_message, dict):
        raise HTTPException(status_code=400, detail="Invalid message")

    message = payload.message

    if message.role != "ROLE_USER":
        raise HTTPException(status_code=400, detail="Invalid message role")

    if len(message.parts) != 1:
        raise HTTPException(
            status_code=400,
            detail="Exactly one message part required",
        )

    part = message.parts[0]
    message_hash = generate_message_hash(raw_message)

    # Check idempotency before handling either an initial message or a
    # continuation. The principal is part of the database key.
    existing = get_processed_message(db, principal, message.messageId)
    replay = replay_or_conflict(existing, message_hash)
    if replay is not None:
        return replay

    is_continuation = bool(message.taskId or message.contextId)

    if is_continuation:
        if not message.taskId or not message.contextId:
            raise HTTPException(
                status_code=400,
                detail="Both taskId and contextId are required",
            )

        if part.mediaType != RESULTS_MEDIA_TYPE:
            raise HTTPException(
                status_code=415,
                detail="Unsupported continuation media type",
            )

        try:
            results_data = ActionResultsData.model_validate(part.data)
        except ValidationError:
            raise HTTPException(status_code=422, detail="Invalid action results")

        task = (
            db.query(Task)
            .filter(
                Task.id == message.taskId,
                Task.owner == principal,
                Task.context_id == message.contextId,
            )
            .first()
        )
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")

        if task.state != "TASK_STATE_INPUT_REQUIRED":
            raise HTTPException(
                status_code=409,
                detail="Task is not waiting for input",
            )

        proposal_data = find_proposal_data(task)
        if not proposal_data:
            raise HTTPException(
                status_code=409,
                detail="Original proposals not found",
            )

        if results_data.batchId != proposal_data.get("batchId"):
            raise HTTPException(status_code=409, detail="Batch ID mismatch")

        proposals = proposal_data.get("proposals", [])
        proposal_map = {
            proposal["packageId"]: proposal
            for proposal in proposals
        }

        result_package_ids = [result.packageId for result in results_data.results]

        # A valid continuation must account for each proposal exactly once.
        if (
            len(result_package_ids) != len(set(result_package_ids))
            or set(result_package_ids) != set(proposal_map.keys())
        ):
            raise HTTPException(
                status_code=400,
                detail="Results do not match proposals",
            )

        executions: list[dict[str, Any]] = []

        for result in results_data.results:
            proposal = proposal_map.get(result.packageId)
            if proposal is None:
                raise HTTPException(status_code=409, detail="Unknown package ID")

            if result.actionId != proposal.get("actionId"):
                raise HTTPException(status_code=409, detail="Action ID mismatch")

            if result.action != proposal.get("action"):
                raise HTTPException(status_code=409, detail="Action mismatch")

            if result.outcome not in ("ACCEPTED", "REJECTED"):
                raise HTTPException(status_code=400, detail="Invalid outcome")

            # Rejected proposals are never included in the execution receipt.
            if result.outcome == "ACCEPTED":
                if not result.receiptNonce or not result.receiptNonce.strip():
                    raise HTTPException(
                        status_code=400,
                        detail="Receipt nonce required for accepted results",
                    )

                executions.append(
                    {
                        "packageId": proposal["packageId"],
                        "actionId": proposal["actionId"],
                        "action": proposal["action"],
                        "receiptNonce": result.receiptNonce,
                        "facts": proposal["facts"],
                        "evidenceRefs": proposal["evidenceRefs"],
                    }
                )

        receipt_artifact = {
            "artifactId": str(uuid.uuid4()),
            "parts": [
                {
                    "mediaType": RECEIPTS_MEDIA_TYPE,
                    "data": {
                        "batchId": results_data.batchId,
                        "executions": executions,
                    },
                }
            ],
        }

        updated_artifacts = list(task.artifacts or [])
        updated_artifacts.append(receipt_artifact)

        updated_history = list(task.history or [])
        updated_history.append(raw_message)

        response_data = {
            "task": {
                "id": task.id,
                "contextId": task.context_id,
                "kind": "task",
                "status": {"state": "TASK_STATE_COMPLETED"},
                "artifacts": updated_artifacts,
                "history": updated_history,
            }
        }

        try:
            # This compare-and-set ensures cancellation and completion cannot
            # both win the transition from INPUT_REQUIRED.
            update_result = db.execute(
                update(Task)
                .where(
                    Task.id == task.id,
                    Task.owner == principal,
                    Task.context_id == message.contextId,
                    Task.state == "TASK_STATE_INPUT_REQUIRED",
                )
                .values(
                    state="TASK_STATE_COMPLETED",
                    artifacts=updated_artifacts,
                    history=updated_history,
                    version=Task.version + 1,
                )
            )

            if update_result.rowcount != 1:
                db.rollback()

                # If this exact continuation committed concurrently, replay it.
                concurrent_existing = get_processed_message(
                    db,
                    principal,
                    message.messageId,
                )
                concurrent_replay = replay_or_conflict(
                    concurrent_existing,
                    message_hash,
                )
                if concurrent_replay is not None:
                    return concurrent_replay

                raise HTTPException(
                    status_code=409,
                    detail="Task was already completed or canceled",
                )

            db.add(
                ProcessedMessage(
                    principal=principal,
                    message_id=message.messageId,
                    request_hash=message_hash,
                    task_id=task.id,
                    response_data=response_data,
                )
            )
            db.commit()

        except IntegrityError:
            db.rollback()
            concurrent_existing = get_processed_message(
                db,
                principal,
                message.messageId,
            )
            concurrent_replay = replay_or_conflict(
                concurrent_existing,
                message_hash,
            )
            if concurrent_replay is not None:
                return concurrent_replay
            raise HTTPException(status_code=409, detail="Continuation conflict")

        except HTTPException:
            db.rollback()
            raise

        except Exception:
            db.rollback()
            raise

        return a2a_response(response_data)

    # Initial message: it must not carry task or context identifiers.
    if part.mediaType != CLAIM_MEDIA_TYPE:
        raise HTTPException(
            status_code=415,
            detail="Unsupported input media type",
        )

    try:
        batch = InvoiceBatchData.model_validate(part.data)
    except ValidationError:
        raise HTTPException(status_code=422, detail="Invalid invoice batch")

    batch_data = batch.model_dump(mode="json")

    # Serialize initial processing within this app process. Recheck after
    # acquiring the lock so a concurrent duplicate does not call the model.
    async with _initial_request_lock:
        existing = get_processed_message(db, principal, message.messageId)
        replay = replay_or_conflict(existing, message_hash)
        if replay is not None:
            return replay

        task_id = str(uuid.uuid4())
        context_id = str(uuid.uuid4())

        try:
            proposal_data = await analyze_invoice_batch(batch_data, db)

            if proposal_data.get("batchId") != batch_data["batchId"]:
                raise ValueError("Agent returned a mismatched batch ID")

            proposals = proposal_data.get("proposals")
            if not isinstance(proposals, list) or len(proposals) != len(
                batch_data["packages"]
            ):
                raise ValueError("Agent returned an incomplete proposal list")

            artifact = {
                "artifactId": str(uuid.uuid4()),
                "parts": [
                    {
                        "mediaType": PROPOSALS_MEDIA_TYPE,
                        "data": proposal_data,
                    }
                ],
            }

            response_data = {
                "task": {
                    "id": task_id,
                    "contextId": context_id,
                    "kind": "task",
                    "status": {"state": "TASK_STATE_INPUT_REQUIRED"},
                    "artifacts": [artifact],
                    "history": [raw_message],
                }
            }

            db.add(
                Task(
                    id=task_id,
                    owner=principal,
                    state="TASK_STATE_INPUT_REQUIRED",
                    context_id=context_id,
                    input_data=batch_data,
                    artifacts=[artifact],
                    history=[raw_message],
                    version=1,
                )
            )

            db.add(
                ProcessedMessage(
                    principal=principal,
                    message_id=message.messageId,
                    request_hash=message_hash,
                    task_id=task_id,
                    response_data=response_data,
                )
            )

            db.commit()

            return a2a_response(response_data)

        except IntegrityError:
            db.rollback()
            existing = get_processed_message(db, principal, message.messageId)
            replay = replay_or_conflict(existing, message_hash)
            if replay is not None:
                return replay
            raise HTTPException(status_code=409, detail="Task creation conflict")

        except HTTPException:
            db.rollback()
            raise

        except Exception:
            db.rollback()
            raise


@app.get("/a2a/tasks/{task_id}")
def get_task(
    task_id: str,
    authorization: str | None = Header(default=None),
    a2a_version: str | None = Header(default=None, alias="A2A-Version"),
    db: Session = Depends(get_db),
) -> JSONResponse:
    principal = authenticate_request(authorization, a2a_version)

    task = (
        db.query(Task)
        .filter(Task.id == task_id, Task.owner == principal)
        .first()
    )
    if task is None:
        # Do not reveal whether a task belonging to another principal exists.
        raise HTTPException(status_code=404, detail="Task not found")

    # Task reads return a Task directly, not {"task": Task}.
    return a2a_response(task_to_dict(task))


@app.get("/a2a/tasks")
def list_tasks(
    authorization: str | None = Header(default=None),
    a2a_version: str | None = Header(default=None, alias="A2A-Version"),
    db: Session = Depends(get_db),
) -> JSONResponse:
    principal = authenticate_request(authorization, a2a_version)

    tasks = (
        db.query(Task)
        .filter(Task.owner == principal)
        .order_by(Task.created_at.desc())
        .all()
    )

    return a2a_response(
        {"tasks": [task_to_dict(task) for task in tasks]}
    )


@app.post("/a2a/tasks/{task_id}:cancel")
def cancel_task(
    task_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
    a2a_version: str | None = Header(default=None, alias="A2A-Version"),
    db: Session = Depends(get_db),
) -> JSONResponse:
    principal = authenticate_request(authorization, a2a_version)

    # Atomic transition: only an INPUT_REQUIRED task can be canceled.
    result = db.execute(
        update(Task)
        .where(
            Task.id == task_id,
            Task.owner == principal,
            Task.state == "TASK_STATE_INPUT_REQUIRED",
        )
        .values(
            state="TASK_STATE_CANCELED",
            version=Task.version + 1,
        )
    )
    db.commit()

    if result.rowcount != 1:
        task = (
            db.query(Task)
            .filter(Task.id == task_id, Task.owner == principal)
            .first()
        )
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")

        raise HTTPException(
            status_code=409,
            detail="Task cannot be canceled in its current state",
        )

    task = (
        db.query(Task)
        .filter(Task.id == task_id, Task.owner == principal)
        .first()
    )

    # Cancellation returns a Task directly, not {"task": Task}.
    return a2a_response(task_to_dict(task))