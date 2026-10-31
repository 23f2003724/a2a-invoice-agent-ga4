from database import SessionLocal, DecisionCache
from agent import canonical_package_hash

package = {
    "packageId": "CACHE-PKG-001",
    "vendorName": "Alpha Supplies",
    "invoiceNumber": "INV-001",
    "amountMinor": 100000,
    "currency": "INR",
    "documents": [
        {"text": "[INV-001] Invoice amount is INR 1,000."},
        {"text": "[PO-001] Purchase order authorizes INR 1,000."},
        {"text": "[GRN-001] Goods received in full."}
    ]
}

db = SessionLocal()

try:
    package_hash = canonical_package_hash(package)
    cached = db.get(DecisionCache, package_hash)

    if cached:
        print("CACHE ENTRY FOUND")
        print("Cached action:", cached.decision_data["action"])
        print("Evidence refs:", cached.decision_data["evidenceRefs"])
    else:
        print("CACHE ENTRY NOT FOUND")

finally:
    db.close()