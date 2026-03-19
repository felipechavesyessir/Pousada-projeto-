const modal = document.getElementById("details-modal");
const closeButton = document.getElementById("close-modal");
const detailButtons = document.querySelectorAll(".detail-btn");

function setText(id, value) {
    const target = document.getElementById(id);
    target.textContent = value && String(value).trim() ? value : "-";
}

function openModal(payload) {
    setText("m-id", `#${payload.id}`);
    setText("m-name", payload.name);
    setText("m-phone", payload.phone);
    setText("m-checkin", payload.checkin);
    setText("m-checkout", payload.checkout);
    setText("m-status", payload.status);
    setText("m-created", payload.created);
    setText("m-notes", payload.notes);

    const receiptLink = document.getElementById("m-receipt");
    receiptLink.href = payload.receiptUrl || "#";

    modal.classList.remove("hidden");
    modal.setAttribute("aria-hidden", "false");
}

function closeModal() {
    modal.classList.add("hidden");
    modal.setAttribute("aria-hidden", "true");
}

detailButtons.forEach((button) => {
    button.addEventListener("click", () => {
        openModal({
            id: button.dataset.id,
            name: button.dataset.name,
            phone: button.dataset.phone,
            checkin: button.dataset.checkin,
            checkout: button.dataset.checkout,
            notes: button.dataset.notes,
            status: button.dataset.status,
            receiptUrl: button.dataset.receiptUrl,
            created: button.dataset.created,
        });
    });
});

closeButton.addEventListener("click", closeModal);

modal.addEventListener("click", (event) => {
    if (event.target === modal) {
        closeModal();
    }
});
