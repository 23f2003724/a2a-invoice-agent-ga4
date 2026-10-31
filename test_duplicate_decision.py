
import httpx
import uuid

url = "http://127.0.0.1:8000/a2a/message:send"

headers = {
    "Authorization": "Bearer local-test-token",
    "A2A-Version": "1.0",
    "Content-Type": "application/a2a+json",
}

message = {
    "messageId": "duplicate-decision-" + uuid.uuid4().hex[:8],
    "role": "ROLE_USER",
    "parts": [
        {
            "mediaType": "application/vnd.ga5.invoice-claim-batch+json",
            "data": {
                "batchId": "duplicate-decision-batch-" + uuid.uuid4().hex[:8],
                "policyRevision": "policy-v1",
                "packages": [
                    {
                        "packageId": "DUP-TEST-001",
                        "vendorName": "Gamma Supplies",
                        "invoiceNumber": "INV-500",
                        "amountMinor": 500000,
                        "currency": "INR",
                        "documents": [
                            {
                                "text": "[INV-500] Gamma Supplies invoice INV-500 requests INR 5,000."
                            },
                            {
                                "text": "[HIST-500] The same vendor and invoice number INV-500 for INR 5,000 was already approved and settled."
                            },
                            {
                                "text": "[PAY-500] Payment record confirms INR 5,000 was paid against invoice INV-500."
                            }
                        ]
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
    timeout=60
)

print("HTTP Status:", response.status_code)

result = response.json()
task = result.get("task", result)

print("Task State:", task.get("status", {}).get("state"))

for artifact in task.get("artifacts", []):
    for part in artifact.get("parts", []):
        data = part.get("data", {})
        if "proposals" in data:
            for proposal in data["proposals"]:
                print("Package:", proposal["packageId"])
                print("Action:", proposal["action"])
                print("Evidence:", proposal["evidenceRefs"])
                print("Rationale:", proposal["rationale"])
