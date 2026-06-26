from flask import Flask, request, jsonify, render_template
from datetime import datetime

app = Flask(__name__)

transactions = [
    {
        "id": 1,
        "amount": 4200.00,
        "description": "Salary - Monthly salary",
        "timestamp": "2026-05-31T08:30:00"
    },
    {
        "id": 2,
        "amount": -1450.00,
        "description": "Housing - Rent",
        "timestamp": "2026-06-01T10:00:00"
    },
    {
        "id": 3,
        "amount": -320.00,
        "description": "Groceries - Weekly shop",
        "timestamp": "2026-06-04T14:00:00"
    },
    {
        "id": 4,
        "amount": -85.00,
        "description": "Food & Dining - Dinner out",
        "timestamp": "2026-06-06T19:00:00"
    },
    {
        "id": 5,
        "amount": -60.00,
        "description": "Transport - Gas",
        "timestamp": "2026-06-07T12:00:00"
    },
    {
        "id": 6,
        "amount": -120.00,
        "description": "Entertainment - Concert tickets",
        "timestamp": "2026-06-11T18:00:00"
    },
    {
        "id": 7,
        "amount": -45.00,
        "description": "Utilities - Internet",
        "timestamp": "2026-06-13T09:00:00"
    },
    {
        "id": 8,
        "amount": 600.00,
        "description": "Freelance - Side project",
        "timestamp": "2026-06-09T11:00:00"
    }
]
next_id = 9

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/transactions", methods=["GET"])
def get_transactions():
    return jsonify(transactions), 200

@app.route("/transactions", methods=["POST"])
def add_transaction():
    global next_id

    if not request.is_json:
        return jsonify({"error": "Request body must be JSON"}), 400

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid or empty JSON body"}), 400

    if "amount" not in data or "description" not in data:
        return jsonify({"error": "Missing 'amount' or 'description'"}), 400

    try:
        amount = float(data["amount"])
    except (ValueError, TypeError):
        return jsonify({"error": "Amount must be a number"}), 400

    description = data["description"]
    if not isinstance(description, str) or not description.strip():
        return jsonify({"error": "Description must be a non-empty string"}), 400

    transaction = {
        "id": next_id,
        "amount": amount,
        "description": description.strip(),
        "timestamp": datetime.now().isoformat()
    }

    transactions.append(transaction)
    next_id += 1

    return jsonify(transaction), 201

@app.route("/transactions/<int:transaction_id>", methods=["DELETE"])
def delete_transaction(transaction_id):
    global transactions
    existing = next((t for t in transactions if t["id"] == transaction_id), None)
    if not existing:
        return jsonify({"error": "Transaction not found"}), 404

    transactions = [t for t in transactions if t["id"] != transaction_id]
    return jsonify({"message": "Deleted"}), 200

if __name__ == "__main__":
    app.run(debug=True)
