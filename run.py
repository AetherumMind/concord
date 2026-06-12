import sys
import json
import sqlite3
from datetime import datetime, timezone

DB = "concord/ledger/registry.db"

def save_receipt(question, answer, confidence=1.0):
    receipt = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "proposition": question,
        "consensus": answer,
        "confidence": confidence,
    }

    conn = sqlite3.connect(DB)
    conn.execute(
        """
        INSERT INTO receipts
        (timestamp, proposition, consensus, confidence, receipt_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            receipt["timestamp"],
            receipt["proposition"],
            receipt["consensus"],
            receipt["confidence"],
            json.dumps(receipt),
        ),
    )
    conn.commit()
    conn.close()
    return receipt

def answer(question):
    q = question.strip().lower()
    if q in {"what is 2+2?", "2+2", "what is 2 + 2?"}:
        return "4"
    return "Placeholder consensus response"

if __name__ == "__main__":
    question = " ".join(sys.argv[1:]).strip()
    if not question:
        question = input("Question: ")

    result = answer(question)
    receipt = save_receipt(question, result)

    print("consensus:", result)
    print("receipt_saved:", receipt["timestamp"])
