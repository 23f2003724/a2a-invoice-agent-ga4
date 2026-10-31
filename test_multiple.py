import httpx
import uuid

url = "http://127.0.0.1:8000/a2a/message:send"

headers = {
    "Authorization": "Bearer local-test-token",
    "A2A-Version": "1.0",
    "Content-Type": "application/a2a+json",
}

message = {
    "messageId": "multi-test-" + uuid.uuid4().hex[:8],
    "role": "ROLE_USER",
    "parts": [
        {
            "mediaType": "application/vnd.ga5.invoice-claim-batch+json",
            "data": {
                "batchId": "multi-batch-001",
                "policyRevision": "policy-v1",
                "packages": [
                    {
                        "packageId": "MULTI-001",
                        "vendorName": "Alpha Supplies",
                        "invoiceNumber": "INV-001",
                        "amountMinor": 100000,
                        "currency": "INR",
                        "documents": [
                            {"text": "[INV-001] Invoice amount is INR 1,000."},
                            {"text": "[PO-001] Purchase order authorizes INR 1,000."},
                            {"text": "[GRN-001] Goods received in full."}
                        ]
                    },
                    {
                        "packageId": "MULTI-002",
                        "vendorName": "Beta Supplies",
                        "invoiceNumber": "INV-002",
                        "amountMinor": 200000,
                        "currency": "INR",
                        "documents": [
                            {"text": "[INV-002] Invoice amount is INR 2,000."},
                            {"text": "[PO-002] Purchase order authorizes INR 2,000."},
                            {"text": "[GRN-002] Goods received in full."}
                        ]
                    }
                ]
            }
        }
    ]
}

response = httpx.post(url, headers=headers, json={"message": message}, timeout=60)
print("HTTP Status:", response.status_code)
result = response.json()
task = result.get("task", result)
print("Task ID:", task.get("id"))
print("Context ID:", task.get("contextId"))
print("Task State:", task.get("status", {}).get("state"))

artifacts = task.get("artifacts", [])
for artifact in artifacts:
    for part in artifact.get("parts", []):
        data = part.get("data", {})
        if "proposals" in data:
            proposals = data["proposals"]
            for p in proposals:
                print(p["packageId"], "Action ID:", p["actionId"])
            print("Proposal Count:", len(proposals))
            for proposal in proposals:
                print(
                    proposal["packageId"],
                    "->",
                    proposal["action"],
                    "| Evidence refs:",
                    len(proposal["evidenceRefs"])
                )