(function () {
    function initPayments() {
        initPixCreationForm();
        initPixCopyButton();
        initPixStatusPolling();
    }

    function initPixCreationForm() {
        const form = document.querySelector("[data-pix-payment-form]");
        if (!form) return;
        const button = form.querySelector('button[type="submit"]');
        const message = form.querySelector("[data-pix-payment-message]");

        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            setButtonLoading(button, true);
            setMessage(message, "Criando pagamento Pix...");
            try {
                const response = await fetch(form.action, {
                    method: "POST",
                    body: new FormData(form),
                    headers: { Accept: "application/json" },
                    credentials: "same-origin"
                });
                const payload = await readJson(response);
                if (!response.ok) throw new Error(payload.error || "Não foi possível criar o Pix.");
                if (!payload.redirect_url) throw new Error("O pagamento foi criado sem uma página de destino.");
                window.location.assign(payload.redirect_url);
            } catch (error) {
                setMessage(message, error.message || "Não foi possível criar o Pix.");
                setButtonLoading(button, false);
            }
        });
    }

    function initPixCopyButton() {
        const button = document.querySelector("[data-copy-pix-code]");
        const field = document.querySelector("[data-pix-copy-code]");
        if (!button || !field) return;
        button.addEventListener("click", async () => {
            const copied = await copyText(field.value, field);
            if (!copied) return;
            const originalHtml = button.innerHTML;
            button.textContent = "Código Pix copiado";
            window.setTimeout(() => { button.innerHTML = originalHtml; }, 2200);
        });
    }

    function initPixStatusPolling() {
        const page = document.querySelector("[data-pix-status-page]");
        const status = page?.querySelector("[data-pix-payment-status]");
        if (!page || !status || !page.dataset.statusUrl) return;
        if (page.dataset.paymentConfirmed === "true") {
            renderApprovedStatus(page, status);
            return;
        }
        const interval = window.setInterval(async () => {
            try {
                const response = await fetch(page.dataset.statusUrl, {
                    headers: { Accept: "application/json" },
                    credentials: "same-origin"
                });
                if (!response.ok) return;
                const payload = await response.json();
                if (payload.approved) {
                    window.clearInterval(interval);
                    renderApprovedStatus(page, status);
                } else if (
                    ["rejected", "cancelled", "canceled", "expired", "refunded", "charged_back"]
                        .includes(payload.status)
                ) {
                    window.clearInterval(interval);
                    status.dataset.status = payload.status;
                    status.textContent = "O pagamento não foi aprovado. Gere um novo Pix para tentar novamente.";
                }
            } catch (_) {
                return;
            }
        }, 3000);
    }

    function renderApprovedStatus(page, status) {
        status.dataset.status = "approved";
        status.textContent = "Pagamento confirmado. Seu BoostConvert PRO está ativo.";
        const accountLink = page.querySelector("[data-pix-account-link]");
        if (accountLink) accountLink.hidden = false;
    }

    async function copyText(text, fallbackField) {
        try {
            await navigator.clipboard.writeText(text);
            return true;
        } catch (_) {
            fallbackField.focus();
            fallbackField.select();
            return document.execCommand("copy");
        }
    }

    async function readJson(response) {
        const contentType = response.headers.get("content-type") || "";
        if (!contentType.includes("application/json")) return {};
        return response.json();
    }

    function setButtonLoading(button, loading) {
        if (!button) return;
        button.disabled = loading;
        button.setAttribute("aria-busy", String(loading));
    }

    function setMessage(message, text) {
        if (message) message.textContent = text || "";
    }

    window.BoostPayments = { initPayments };
    document.addEventListener("DOMContentLoaded", initPayments);
})();
