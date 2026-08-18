(function () {
    "use strict";

    const DEFAULT_BUTTON_TEXT = "Assinar BoostConvert PRO";

    function initPayments() {
        document.querySelectorAll("[data-payment-checkout]").forEach(bindCheckoutForm);
    }

    function bindCheckoutForm(form) {
        if (form.dataset.paymentBound === "true") return;
        form.dataset.paymentBound = "true";
        form.addEventListener("submit", (event) => submitCheckout(event, form));
    }

    async function submitCheckout(event, form) {
        event.preventDefault();
        const button = form.querySelector("[data-payment-button]");
        const message = form.querySelector("[data-payment-message]");
        if (!button || button.disabled) return;

        setLoading(button, message, true);
        try {
            const payload = Object.fromEntries(new FormData(form).entries());
            const response = await fetch(form.action, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    Accept: "application/json",
                    "Content-Type": "application/json",
                    "X-CSRF-Token": String(payload._csrf_token || ""),
                    "X-Idempotency-Key": String(payload.idempotency_key || "")
                },
                body: JSON.stringify({
                    plan_id: payload.plan_id,
                    replace_unpaid_subscription: form.dataset.replaceUnpaidSubscription === "true"
                })
            });
            if (response.redirected && response.url.includes("/login")) {
                window.location.assign(form.dataset.loginUrl || response.url);
                return;
            }

            const result = await readJson(response);
            if (!response.ok) {
                const error = new Error(result.error || checkoutError(response.status));
                error.canReplace = result.can_replace === true;
                throw error;
            }
            if (!isHostedCheckoutUrl(result.checkout_url)) {
                throw new Error("O provedor retornou uma resposta inválida.");
            }
            window.location.assign(result.checkout_url);
        } catch (error) {
            if (error.canReplace) {
                form.dataset.replaceUnpaidSubscription = "true";
                if (message) {
                    message.textContent = "Há uma tentativa anterior sem pagamento confirmado. Clique em “Reiniciar pagamento” para cancelá-la e abrir um novo checkout.";
                }
            } else if (message) {
                message.textContent = error.message || "Não foi possível iniciar sua assinatura.";
            }
            renewIdempotencyKey(form);
            setLoading(button, message, false, true);
        }
    }

    async function readJson(response) {
        const contentType = response.headers.get("content-type") || "";
        if (!contentType.includes("application/json")) {
            if (response.status === 401 || response.status === 403) {
                throw new Error("Entre na sua conta para continuar.");
            }
            throw new Error("Resposta inválida ao iniciar o pagamento.");
        }
        return response.json();
    }

    function isHostedCheckoutUrl(value) {
        try {
            const url = new URL(String(value));
            return url.protocol === "https:" && (
                url.hostname === "mercadopago.com" ||
                url.hostname.endsWith(".mercadopago.com") ||
                url.hostname === "mercadopago.com.br" ||
                url.hostname.endsWith(".mercadopago.com.br")
            );
        } catch (error) {
            return false;
        }
    }

    function checkoutError(status) {
        if (status === 401 || status === 403) return "Entre na sua conta para continuar.";
        if (status === 429) return "Muitas tentativas. Aguarde um minuto e tente novamente.";
        return "Não foi possível iniciar sua assinatura. Tente novamente.";
    }

    function renewIdempotencyKey(form) {
        const field = form.querySelector("[data-payment-idempotency]");
        if (field && window.crypto?.randomUUID) field.value = window.crypto.randomUUID();
    }

    function setLoading(button, message, loading, preserveMessage) {
        button.disabled = loading;
        button.setAttribute("aria-busy", String(loading));
        const readyText = formButtonText(button);
        button.textContent = loading ? "Abrindo assinatura segura..." : readyText;
        if (message && !preserveMessage) message.textContent = "";
    }

    function formButtonText(button) {
        const form = button.closest("form");
        return form?.dataset.replaceUnpaidSubscription === "true"
            ? "Reiniciar pagamento"
            : DEFAULT_BUTTON_TEXT;
    }

    window.BoostPayments = { initPayments };
}());
