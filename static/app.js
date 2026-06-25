const amountInput = document.getElementById("amount");
const descriptionInput = document.getElementById("description");
const addButton = document.getElementById("addButton");
const list = document.getElementById("list");
const messageDiv = document.getElementById("message");

async function loadTransactions() {
    const res = await fetch("/transactions");
    if (!res.ok) {
        messageDiv.textContent = "Failed to load transactions.";
        return;
    }

    const data = await res.json();
    list.innerHTML = "";

    if (!data.length) {
        list.innerHTML = "<li>No transactions yet.</li>";
        return;
    }

    data.forEach(t => {
        const item = document.createElement("li");
        const left = document.createElement("span");
        left.innerHTML = `<span class="amount">$${Number(t.amount).toFixed(2)}</span> - ${t.description} <small>${new Date(t.timestamp).toLocaleString()}</small>`;

        const deleteButton = document.createElement("button");
        deleteButton.className = "delete-btn";
        deleteButton.textContent = "Delete";
        deleteButton.addEventListener("click", () => deleteTransaction(t.id));

        item.appendChild(left);
        item.appendChild(deleteButton);
        list.appendChild(item);
    });
}

async function addTransaction() {
    const amount = parseFloat(amountInput.value);
    const description = descriptionInput.value.trim();

    if (!description) {
        messageDiv.textContent = "Description is required.";
        return;
    }
    if (Number.isNaN(amount)) {
        messageDiv.textContent = "Amount must be a valid number.";
        return;
    }

    const res = await fetch("/transactions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ amount, description })
    });

    const result = await res.json();
    if (!res.ok) {
        messageDiv.textContent = result.error || "Failed to add transaction.";
        return;
    }

    amountInput.value = "";
    descriptionInput.value = "";
    messageDiv.textContent = "Transaction added.";
    loadTransactions();
}

async function deleteTransaction(id) {
    const res = await fetch(`/transactions/${id}`, { method: "DELETE" });
    const result = await res.json();

    if (!res.ok) {
        messageDiv.textContent = result.error || "Failed to delete transaction.";
        return;
    }

    messageDiv.textContent = "Transaction deleted.";
    loadTransactions();
}

addButton.addEventListener("click", addTransaction);
loadTransactions();
