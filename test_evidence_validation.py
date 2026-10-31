import asyncio
import agent

class FakeDB:
    def get(self, *args):
        return None

    def merge(self, item):
        pass

package = {
    "packageId": "IRRELEVANT-REF-001",
    "vendorName": "Test Supplies",
    "invoiceNumber": "INV-IRR",
    "amountMinor": 100000,
    "currency": "INR",
    "documents": [
        {"text": "[INV-IRR] Invoice requests INR 1,000."},
        {"text": "[PO-IRR] Purchase order authorizes INR 1,000."},
        {"text": "[GRN-IRR] Goods received in full."},
        {"text": "[OLD-NEWS] Office cafeteria will remain closed on Friday."}
    ]
}

async def fake_ai(prompt, system_prompt=None):
    return """
    {
      "proposals": [{
        "packageId": "IRRELEVANT-REF-001",
        "action": "settle_invoice",
        "facts": {
          "vendorName": "Test Supplies",
          "invoiceNumber": "INV-IRR",
          "amountMinor": 100000,
          "currency": "INR"
        },
        "evidenceRefs": [
            "[INV-IRR]",
            "[PO-IRR]",
            "[OLD-NEWS]"
        ],
        "rationale": "The invoice matches the purchase order [INV-IRR] and the goods receipt [PO-IRR]. The office cafeteria notice [OLD-NEWS] is also included. Therefore settle_invoice is proposed."
      }]
    }
    """

async def main():
    original = agent.ask_aipipe
    agent.ask_aipipe = fake_ai

    try:
        await agent.analyze_invoice_batch({
            "batchId": "irrelevant-ref-batch",
            "packages": [package]
        }, FakeDB())

        print("RESULT: Irrelevant evidence was ACCEPTED")

    except ValueError as e:
        print("RESULT: Evidence rejected:", e)

    finally:
        agent.ask_aipipe = original

asyncio.run(main())