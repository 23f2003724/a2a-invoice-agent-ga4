
import httpx

url = "http://127.0.0.1:8000/a2a/message:send"

headers = {
    "Authorization": "Bearer local-test-token",
    "A2A-Version": "1.0",
    "Content-Type": "application/a2a+json",
}

message = {
    "messageId": "duplicate-receipt-test-001",
    "taskId": "30f4d4fa-d21b-488e-a984-33aec3aa567a",
    "contextId": "f9c9c0b0-6748-4b11-9db8-76d2bd324d4e",
    "role": "ROLE_USER",
    "parts": [
        {
            "mediaType": "application/vnd.ga5.invoice-action-results+json",
            "data": {
                "batchId": "multi-batch-001",
                "results": [
                    {
                        "packageId": "MULTI-001",
                        "actionId": "01ae30383a164296bf03a3c3f88e327f",
                        "action": "settle_invoice",
                        "outcome": "ACCEPTED",
                        "receiptNonce": "duplicate-test-nonce-001"
                    },
                    {
                        "packageId": "MULTI-002",
                        "actionId": "7d91df39c95545449c6c87db789512b0",
                        "action": "settle_invoice",
                        "outcome": "ACCEPTED",
                        "receiptNonce": "duplicate-test-nonce-002"
                    }
                ]
            }
        }
    ]
}

for attempt in range(1, 3):
    response = httpx.post(
        url,
        headers=headers,
        json={"message": message},
        timeout=30
    )

    print(f"\nAttempt {attempt}")
    print("HTTP Status:", response.status_code)

    result = response.json()
    task = result.get("task", result)

    print("Task State:", task.get("status", {}).get("state"))
    print("Artifact Count:", len(task.get("artifacts", [])))

    for artifact in task.get("artifacts", []):
        for part in artifact.get("parts", []):
            if part.get("mediaType") == "application/vnd.ga5.invoice-action-receipts+json":
                print("Receipt executions:", len(part["data"]["executions"]))
