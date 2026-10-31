
import httpx

url = "http://127.0.0.1:8000/a2a/message:send"

headers = {
    "Authorization": "Bearer local-test-token",
    "A2A-Version": "1.0",
    "Content-Type": "application/a2a+json",
}

message = {
    "messageId": "invalid-context-test-001",
    "taskId": "e96126ef-f56b-418c-b575-a9c858998b34",
    "contextId": "wrong-context-id",
    "role": "ROLE_USER",
    "parts": [
        {
            "mediaType": "application/vnd.ga5.invoice-action-results+json",
            "data": {
                "batchId": "multi-batch-001",
                "results": [
                    {
                        "packageId": "MULTI-001",
                        "actionId": "09ca833b935649fc87833e1a5aac2bfb",
                        "action": "settle_invoice",
                        "outcome": "ACCEPTED",
                        "receiptNonce": "invalid-context-nonce-001"
                    },
                    {
                        "packageId": "MULTI-002",
                        "actionId": "293f85c978584857899f68c7efebee95",
                        "action": "settle_invoice",
                        "outcome": "ACCEPTED",
                        "receiptNonce": "invalid-context-nonce-002"
                    }
                ]
            }
        }
    ]
}

response = httpx.post(
    url,
    headers=headers,
    json={"message": message},
    timeout=30
)

print("HTTP Status:", response.status_code)
print("Response:", response.text)
