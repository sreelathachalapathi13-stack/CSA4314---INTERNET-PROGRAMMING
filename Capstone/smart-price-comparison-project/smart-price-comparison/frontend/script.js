const API_BASE = "http://127.0.0.1:5000/api";
let currentQuery = "";
let chartInstance = null;

document.getElementById("searchInput").addEventListener("keypress", function (e) {
    if (e.key === "Enter") {
        searchProduct();
    }
});

async function searchProduct() {
    const query = document.getElementById("searchInput").value.trim();
    if (!query) return;

    currentQuery = query;
    document.getElementById("loader").classList.remove("hidden");
    document.getElementById("recommendationBanner").classList.add("hidden");
    document.getElementById("comparisonGrid").classList.add("hidden");
    document.getElementById("alertAndChartSection").classList.add("hidden");

    try {
        const response = await fetch(`${API_BASE}/compare?q=${encodeURIComponent(query)}`);
        const data = await response.json();

        renderComparison(data);
        loadHistoryChart(query);
    } catch (error) {
        alert("Failed to connect to backend server. Ensure Flask is running on port 5000.");
        console.error(error);
    } finally {
        document.getElementById("loader").classList.add("hidden");
    }
}

function renderComparison(data) {
    const { amazon, flipkart, recommendation } = data;

    // Reset winner highlight
    document.getElementById("amazonCard").classList.remove("winner");
    document.getElementById("flipkartCard").classList.remove("winner");

    // Populate Amazon
    document.getElementById("amazonTitle").innerText = amazon.title;
    document.getElementById("amazonPrice").innerText = amazon.price ? `₹${amazon.price.toLocaleString("en-IN")}` : "Check Live Price";
    document.getElementById("amazonLink").href = amazon.url;
    const aImg = document.getElementById("amazonImg");
    if (amazon.image) {
        aImg.src = amazon.image;
        aImg.classList.remove("hidden");
    } else {
        aImg.classList.add("hidden");
    }

    // Populate Flipkart
    document.getElementById("flipkartTitle").innerText = flipkart.title;
    document.getElementById("flipkartPrice").innerText = flipkart.price ? `₹${flipkart.price.toLocaleString("en-IN")}` : "Check Live Price";
    document.getElementById("flipkartLink").href = flipkart.url;
    const fImg = document.getElementById("flipkartImg");
    if (flipkart.image) {
        fImg.src = flipkart.image;
        fImg.classList.remove("hidden");
    } else {
        fImg.classList.add("hidden");
    }

    // Recommendation Banner
    const banner = document.getElementById("recommendationBanner");
    if (recommendation) {
        const savingsText = recommendation.savings > 0 ? ` (You save ₹${recommendation.savings.toLocaleString("en-IN")})` : "";
        banner.innerHTML = `
            <div>
                <strong>Lowest Price Suggested:</strong> Buy from <strong>${recommendation.best_platform}</strong> at 
                <strong>₹${recommendation.lowest_price.toLocaleString("en-IN")}</strong>${savingsText}
            </div>
            <a href="${recommendation.buy_url}" target="_blank" rel="noopener noreferrer">Order Now on ${recommendation.best_platform}</a>
        `;
        banner.classList.remove("hidden");

        if (recommendation.best_platform === "Amazon") {
            document.getElementById("amazonCard").classList.add("winner");
        } else if (recommendation.best_platform === "Flipkart") {
            document.getElementById("flipkartCard").classList.add("winner");
        }
    }

    document.getElementById("comparisonGrid").classList.remove("hidden");
    document.getElementById("alertAndChartSection").classList.remove("hidden");
}

async function submitAlert(event) {
    event.preventDefault();
    const email = document.getElementById("alertEmail").value;
    const targetPrice = document.getElementById("targetPrice").value;

    const res = await fetch(`${API_BASE}/alerts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            email: email,
            product_query: currentQuery,
            target_price: targetPrice
        })
    });

    const data = await res.json();
    document.getElementById("alertStatus").innerText = data.message || data.error;
}

async function loadHistoryChart(query) {
    const res = await fetch(`${API_BASE}/history?q=${encodeURIComponent(query)}`);
    const rows = await res.json();

    const labels = rows.map(r => new Date(r.recorded_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
    const amazonPrices = rows.map(r => r.platform === "Amazon" ? r.price : null);
    const flipkartPrices = rows.map(r => r.platform === "Flipkart" ? r.price : null);

    const ctx = document.getElementById("priceChart").getContext("2d");
    if (chartInstance) chartInstance.destroy();

    chartInstance = new Chart(ctx, {
        type: "line",
        data: {
            labels: labels,
            datasets: [
                {
                    label: "Amazon (₹)",
                    data: amazonPrices,
                    borderColor: "#f59e0b",
                    spanGaps: true,
                    tension: 0.2
                },
                {
                    label: "Flipkart (₹)",
                    data: flipkartPrices,
                    borderColor: "#2563eb",
                    spanGaps: true,
                    tension: 0.2
                }
            ]
        }
    });
}
