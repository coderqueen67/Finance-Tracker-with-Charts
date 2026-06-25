from flask import Flask, request, jsonify, render_template
from datetime import datetime

app = Flask(__name__)

transactions = []
next_id = 1

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
