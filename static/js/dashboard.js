const modal = document.getElementById("details-modal");
const closeButton = document.getElementById("close-modal");
const detailButtons = document.querySelectorAll(".detail-btn");
const manualWhatsappButtons = document.querySelectorAll(".manual-whatsapp-btn");

function buildWhatsappLink(name, phone) {
    const digits = String(phone || "")
        .replace("whatsapp:", "")
        .replace(/\D/g, "");

    if (!digits) {
        return "";
    }

    const message = `Ola, ${name}. Recebemos sua reserva na Pousada Sovereign e vamos validar seu comprovante. Obrigado pelo contato.`;
    return `https://wa.me/${digits}?text=${encodeURIComponent(message)}`;
}

function setText(id, value) {
    const target = document.getElementById(id);
    target.textContent = value && String(value).trim() ? value : "-";
}

function openModal(payload) {
    setText("m-id", `#${payload.id}`);
    setText("m-name", payload.name);
    setText("m-phone", payload.phone);
    setText("m-cpf", payload.cpf);
    setText("m-room", payload.room);
    setText("m-entry", payload.entryAmount ? `R$ ${payload.entryAmount}` : "-");
    setText("m-checkin", payload.checkin);
    setText("m-checkout", payload.checkout);
    setText("m-status", payload.status);
    setText("m-created", payload.created);
    setText("m-notes", payload.notes);

    const receiptLink = document.getElementById("m-receipt");
    receiptLink.href = payload.receiptUrl || "#";
    receiptLink.textContent = payload.receiptUrl ? "Abrir arquivo" : "Sem comprovante";

    const receiptDownloadLink = document.getElementById("m-receipt-download");
    receiptDownloadLink.href = payload.receiptDownloadUrl || "#";
    receiptDownloadLink.textContent = payload.receiptDownloadUrl ? "Baixar comprovante" : "Sem arquivo para baixar";

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
            cpf: button.dataset.cpf,
            room: button.dataset.room,
            entryAmount: button.dataset.entryAmount,
            checkin: button.dataset.checkin,
            checkout: button.dataset.checkout,
            notes: button.dataset.notes,
            status: button.dataset.status,
            receiptUrl: button.dataset.receiptUrl,
            receiptDownloadUrl: button.dataset.receiptDownloadUrl,
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

manualWhatsappButtons.forEach((button) => {
    button.addEventListener("click", () => {
        const link = buildWhatsappLink(button.dataset.name, button.dataset.phone);

        if (!link) {
            button.classList.add("disabled");
            button.textContent = "Sem WhatsApp valido";
            return;
        }

        window.open(link, "_blank", "noopener");
    });
});
