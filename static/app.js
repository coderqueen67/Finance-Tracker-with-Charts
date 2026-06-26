const amountInput = document.getElementById("amount");
const descriptionInput = document.getElementById("description");
const openModalButton = document.getElementById("openModal");
const closeModalButton = document.getElementById("closeModal");
const cancelModalButton = document.getElementById("cancelModal");
const transactionDialog = document.getElementById("transactionDialog");
const transactionForm = document.getElementById("transactionForm");
const transactionsContainer = document.getElementById("transactions");
const messageDiv = document.getElementById("message");
const balanceChartCanvas = document.getElementById("balanceChart");
let balanceChart;

async function loadTransactions() {
    const res = await fetch("/transactions");
    if (!res.ok) {
        messageDiv.textContent = "Failed to load transactions.";
        return;
    }

    const data = await res.json();
    transactionsContainer.innerHTML = "";

    if (!data.length) {
        transactionsContainer.innerHTML = "<p>No transactions yet.</p>";
        updateChart([]);
        return;
    }

    const sortedList = data.slice().sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
    sortedList.forEach(t => {
        const [title, note] = t.description.includes(" - ")
            ? t.description.split(" - ")
            : [t.description, ""];

        const item = document.createElement("article");
        item.className = "transaction";
        item.innerHTML = `
            <span class="trend ${t.amount >= 0 ? "income" : "expense"}" aria-hidden="true">
                ${t.amount >= 0
                    ? '<svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 17H7V7" /><path d="M17 7 7 17" /></svg>'
                    : '<svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 7h10v10" /><path d="M7 17 17 7" /></svg>'}
            </span>
            <div>
              <h3 class="transaction-title">${title}</h3>
              <p class="transaction-note">${note}</p>
            </div>
            <p class="transaction-money ${t.amount >= 0 ? "positive" : ""}">
              ${t.amount >= 0 ? "+" : "-"}${new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Math.abs(t.amount))}
              <span class="date">${new Date(t.timestamp).toLocaleDateString("en-US", { month: "short", day: "numeric" })}</span>
            </p>
        `;

        transactionsContainer.appendChild(item);
    });

    updateChart(data);
}

function updateChart(transactions) {
    const sorted = transactions.slice().sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
    const labels = [];
    const cumulative = [];
    let balance = 0;

    sorted.forEach(t => {
        balance += Number(t.amount);
        labels.push(new Date(t.timestamp).toLocaleString());
        cumulative.push(balance.toFixed(2));
    });

    const chartData = {
        labels,
        datasets: [
            {
                label: "Balance",
                data: cumulative,
                borderColor: "#1f77b4",
                backgroundColor: "rgba(31, 119, 180, 0.2)",
                tension: 0.3,
                fill: true,
                pointRadius: 4,
            }
        ]
    };

    const config = {
        type: "line",
        data: chartData,
        options: {
            responsive: true,
            plugins: {
                legend: { display: false },
                tooltip: { mode: "index", intersect: false }
            },
            scales: {
                x: {
                    title: { display: true, text: "Time" }
                },
                y: {
                    title: { display: true, text: "Balance" }
                }
            }
        }
    };

    if (balanceChart) {
        balanceChart.data = chartData;
        balanceChart.options = config.options;
        balanceChart.update();
    } else {
        balanceChart = new Chart(balanceChartCanvas, config);
    }
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
    transactionDialog.close();
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

openModalButton.addEventListener("click", () => transactionDialog.showModal());
closeModalButton.addEventListener("click", () => transactionDialog.close());
cancelModalButton.addEventListener("click", () => transactionDialog.close());
transactionForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await addTransaction();
});

loadTransactions();
