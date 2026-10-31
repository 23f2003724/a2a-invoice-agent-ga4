from main import a2a_response
from fastapi import HTTPException

data = {"test": "x" * (520 * 1024)}

try:
    a2a_response(data)
    print("ERROR: Oversized response was not rejected")

except HTTPException as e:
    print("HTTP Status:", e.status_code)
    print("Detail:", e.detail)