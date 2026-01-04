// ================= PROFILE DROPDOWN =================
const profileBtn = document.getElementById("profileBtn");
const profileMenu = document.getElementById("profileMenu");

if (profileBtn && profileMenu) {
    // Toggle dropdown on click
    profileBtn.addEventListener("click", (e) => {
        e.stopPropagation(); // Prevent click from propagating to window
        profileMenu.classList.toggle("show");
    });

    // Close dropdown when clicking outside
    window.addEventListener("click", (e) => {
        if (!e.target.closest(".profile-wrapper")) {
            profileMenu.classList.remove("show");
        }
    });
}

// ================= LIVE SEARCH =================
const searchInput = document.querySelector(".search-bar");

if (searchInput) {
    searchInput.addEventListener("input", () => {
        const filter = searchInput.value.toLowerCase();

        // Filter novel cards
        const cards = document.querySelectorAll(".novel-card");
        cards.forEach(card => {
            const titleEl = card.querySelector("h3") || card.querySelector("h4");
            const descEl = card.querySelector("p");
            const title = titleEl ? titleEl.textContent.toLowerCase() : "";
            const description = descEl ? descEl.textContent.toLowerCase() : "";

            if (title.includes(filter) || description.includes(filter)) {
                card.style.display = "";
            } else {
                card.style.display = "none";
            }
        });

        // Filter admin users table (if on admin page)
        const adminTableRows = document.querySelectorAll(".admin-table tbody tr");
        adminTableRows.forEach(row => {
            const usernameCell = row.querySelector("td:nth-child(2)")?.textContent.toLowerCase() || "";
            const emailCell = row.querySelector("td:nth-child(3)")?.textContent.toLowerCase() || "";

            if (usernameCell.includes(filter) || emailCell.includes(filter)) {
                row.style.display = "";
            } else {
                row.style.display = "none";
            }
        });
    });
}
