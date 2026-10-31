
import httpx
import uuid

url = "http://127.0.0.1:8000/a2a/message:send"

headers = {
    "Authorization": "Bearer local-test-token",
    "A2A-Version": "1.0",
    "Content-Type": "application/a2a+json",
}

message = {
    "messageId": "different-invoice-" + uuid.uuid4().hex[:8],
    "role": "ROLE_USER",
    "parts": [
        {
            "mediaType": "application/vnd.ga5.invoice-claim-batch+json",
            "data": {
                "batchId": "different-invoice-batch-" + uuid.uuid4().hex[:8],
                "policyRevision": "policy-v1",
                "packages": [
                    {
                        "packageId": "DIFF-INV-001",
                        "vendorName": "Gamma Supplies",
                        "invoiceNumber": "INV-501",
                        "amountMinor": 500000,
                        "currency": "INR",
                        "documents": [
                            {"text": "[INV-501] New invoice INV-501 requests INR 5,000."},
                            {"text": "[PO-501] Purchase order authorizes INR 5,000."},
                            {"text": "[GRN-501] Goods received in full."}
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
            for p in data["proposals"]:
                print("Action:", p["action"])
                print("Evidence:", p["evidenceRefs"])
                print("Rationale:", p["rationale"])
