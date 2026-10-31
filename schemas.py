
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BaseSchema(BaseModel):
    model_config = ConfigDict(extra="allow")


class Part(BaseSchema):
    mediaType: str = Field(min_length=1)
    data: dict[str, Any]



class Message(BaseSchema):
    messageId: str = Field(min_length=1)

    taskId: str | None = None

    contextId: str | None = None

    role: str = Field(min_length=1)

    parts: list[Part]


class Configuration(BaseSchema):
    returnImmediately: bool = False

    historyLength: int = Field(
        default=20,
        ge=0
    )

    acceptedOutputModes: list[str] = Field(
        default_factory=list
    )


class SendMessageRequest(BaseSchema):
    message: Message

    configuration: Configuration = Field(
        default_factory=Configuration
    )


class TaskRequest(BaseSchema):
    id: str = Field(min_length=1)


class TaskStatus(BaseSchema):
    state: str


class Artifact(BaseSchema):
    artifactId: str = Field(min_length=1)

    parts: list[Part]


class Task(BaseSchema):
    id: str = Field(min_length=1)

    contextId: str = Field(min_length=1)

    kind: str = "task"

    status: TaskStatus

    artifacts: list[Artifact] = Field(
        default_factory=list
    )

    history: list[Message] = Field(
        default_factory=list
    )


class InvoiceBatchData(BaseSchema):
    batchId: str = Field(min_length=1)

    policyRevision: str = Field(min_length=1)

    packages: list[dict[str, Any]] = Field(
        min_length=1
    )


class ActionResult(BaseSchema):
    packageId: str = Field(min_length=1)

    actionId: str = Field(min_length=12)

    action: str = Field(min_length=1)

    outcome: str

    receiptNonce: str | None = None


class ActionResultsData(BaseSchema):
    batchId: str = Field(min_length=1)

    results: list[ActionResult] = Field(
        min_length=1
    )
