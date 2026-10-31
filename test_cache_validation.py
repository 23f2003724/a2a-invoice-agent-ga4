
import asyncio
import agent

class FakeDB:
    def __init__(self):
        self.ai_cache_saved = []

    def get(self, model, package_hash):
        return type("Cached", (), {
            "decision_data": {
                "action": "settle_invoice",
                "facts": {
                    "vendorName": "Test Supplies",
                    "invoiceNumber": "INV-CACHE",
                    "amountMinor": 100000,
                    "currency": "INR"
                },
                "evidenceRefs": [
                    "[INV-CACHE]",
                    "[PO-CACHE]",
                    "[FAKE-OLD-REF]"
                ],
                "rationale": (
                    "The invoice matches the purchase order "
                    "[INV-CACHE] and goods receipt [PO-CACHE], "
                    "so settle_invoice is proposed."
                )
            }
        })()

    def merge(self, item):
        self.ai_cache_saved.append(item)


package = {
    "packageId": "CACHE-VALIDATION-001",
    "vendorName": "Test Supplies",
    "invoiceNumber": "INV-CACHE",
    "amountMinor": 100000,
    "currency": "INR",
    "documents": [
        {"text": "[INV-CACHE] Invoice requests INR 1,000."},
        {"text": "[PO-CACHE] Purchase order authorizes INR 1,000."},
        {"text": "[GRN-CACHE] Goods received in full."}
    ]
}


async def main():
    db = FakeDB()
    original_ai = agent.ask_aipipe
    ai_called = False

    async def fake_ai(prompt, system_prompt=None):
        nonlocal ai_called
        ai_called = True

        return """
        {
          "proposals": [{
            "packageId": "CACHE-VALIDATION-001",
            "action": "settle_invoice",
            "facts": {
              "vendorName": "Test Supplies",
              "invoiceNumber": "INV-CACHE",
              "amountMinor": 100000,
              "currency": "INR"
            },
            "evidenceRefs": [
              "[INV-CACHE]",
              "[PO-CACHE]",
              "[GRN-CACHE]"
            ],
            "rationale": "The invoice [INV-CACHE] matches the purchase order [PO-CACHE], and the goods receipt [GRN-CACHE] confirms delivery. Therefore settle_invoice is proposed."
          }]
        }
        """

    agent.ask_aipipe = fake_ai

    try:
        result = await agent.analyze_invoice_batch({
            "batchId": "CACHE-TEST-BATCH",
            "packages": [package]
        }, db)

        print("AI called:", ai_called)
        print(
            "Final evidence references:",
            result["proposals"][0]["evidenceRefs"]
        )

        if ai_called:
            print("PASS: Invalid cached decision was rejected.")
        else:
            print("FAIL: Invalid cached decision was reused.")

    except Exception as e:
        print("TEST ERROR:", repr(e))

    finally:
        agent.ask_aipipe = original_ai


asyncio.run(main())
