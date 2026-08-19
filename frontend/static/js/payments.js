(function () {
    "use strict";

    let cardBrickController = null;
    let cardBrickInitializing = false;
    let cardSubmissionInFlight = false;

    function initPayments() {
        initCardPaymentBrick();
        initPaymentStatusPolling();
    }

    async function initCardPaymentBrick() {
        const config = document.querySelector("[data-card-payment-config]");
        const container = document.getElementById("cardPaymentBrick_container");
        if (!config || !container || cardBrickController || cardBrickInitializing) return;

        const message = document.querySelector("[data-card-payment-message]");
        const publicKey = String(config.dataset.publicKey || "").trim();
        if (!publicKey || !window.MercadoPago) {
            setMessage(message, "O pagamento seguro por cartão está temporariamente indisponível.");
            return;
        }

        cardBrickInitializing = true;
        let idempotencyKey = config.dataset.idempotencyKey;
        try {
            const amount = Number(config.dataset.amount);
            const mercadoPago = new window.MercadoPago(publicKey, { locale: "pt-BR" });
            const bricksBuilder = mercadoPago.bricks();
            cardBrickController = await bricksBuilder.create("cardPayment", container.id, {
                initialization: {
                    amount,
                    payer: { email: config.dataset.payerEmail }
                },
                customization: {
                    visual: { style: { theme: "default" } },
                    paymentMethods: {
                        types: { excluded: ["debit_card", "prepaid_card"] },
                        maxInstallments: Number(config.dataset.maxInstallments || 12)
                    }
                },
                callbacks: {
                    onReady: () => setMessage(message, ""),
                    onSubmit: async (formData) => {
                        if (cardSubmissionInFlight) return;
                        cardSubmissionInFlight = true;
                        let redirecting = false;
                        setMessage(message, "Processando pagamento com segurança...");
                        try {
                            const response = await fetch(config.dataset.endpoint, {
                                method: "POST",
                                credentials: "same-origin",
                                headers: {
                                    Accept: "application/json",
                                    "Content-Type": "application/json",
                                    "X-CSRF-Token": config.dataset.csrfToken,
                                    "X-Idempotency-Key": idempotencyKey
                                },
                                body: JSON.stringify(buildCardPayload(formData))
                            });
                            const result = await readJson(response);
                            if (!response.ok) {
                                idempotencyKey = createUuid();
                                throw new Error(result.error || "Não foi possível processar o pagamento.");
                            }
                            if (!result.redirect_url) {
                                throw new Error("Pagamento criado sem página de status.");
                            }
                            redirecting = true;
                            window.location.assign(result.redirect_url);
                        } catch (error) {
                            setMessage(message, error.message || "Não foi possível processar o pagamento.");
                            throw error;
                        } finally {
                            if (!redirecting) cardSubmissionInFlight = false;
                        }
                    },
                    onError: () => {
                        setMessage(message, "Não foi possível processar o cartão. Revise os dados e tente novamente.");
                    }
                }
            });
        } catch (_) {
            setMessage(message, "Não foi possível iniciar o pagamento seguro por cartão.");
        } finally {
            cardBrickInitializing = false;
        }
    }

    function buildCardPayload(formData) {
        const payer = formData && typeof formData.payer === "object" ? formData.payer : {};
        const payload = {
            token: String(formData?.token || ""),
            payment_method_id: String(formData?.payment_method_id || ""),
            issuer_id: String(formData?.issuer_id || ""),
            installments: Number(formData?.installments || 0),
            payer: {}
        };
        if (payer.identification?.type && payer.identification?.number) {
            payload.payer.identification = {
                type: String(payer.identification.type),
                number: String(payer.identification.number)
            };
        }
        return payload;
    }

    function initPaymentStatusPolling() {
        const page = document.querySelector("[data-payment-status-page]");
        const status = page?.querySelector("[data-payment-status]");
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
                const result = await response.json();
                if (result.approved) {
                    window.clearInterval(interval);
                    renderApprovedStatus(page, status);
                } else if (["rejected", "canceled", "refunded", "charged_back"].includes(result.status)) {
                    window.clearInterval(interval);
                    status.dataset.status = result.status;
                    status.textContent = "O pagamento não foi aprovado ou deixou de ser válido.";
                    const retryLink = page.querySelector("[data-payment-retry-link]");
                    if (retryLink) retryLink.hidden = false;
                }
            } catch (_) {
                return;
            }
        }, 3000);
    }

    function renderApprovedStatus(page, status) {
        status.dataset.status = "approved";
        status.textContent = "Pagamento aprovado. Seu BoostConvert PRO está ativo por 30 dias.";
        const accountLink = page.querySelector("[data-payment-account-link]");
        if (accountLink) accountLink.hidden = false;
    }

    async function readJson(response) {
        const contentType = response.headers.get("content-type") || "";
        return contentType.includes("application/json") ? response.json() : {};
    }

    function createUuid() {
        if (window.crypto?.randomUUID) return window.crypto.randomUUID();
        const bytes = new Uint8Array(16);
        window.crypto.getRandomValues(bytes);
        bytes[6] = (bytes[6] & 0x0f) | 0x40;
        bytes[8] = (bytes[8] & 0x3f) | 0x80;
        const hex = Array.from(bytes, (value) => value.toString(16).padStart(2, "0"));
        return `${hex.slice(0, 4).join("")}-${hex.slice(4, 6).join("")}-${hex.slice(6, 8).join("")}-${hex.slice(8, 10).join("")}-${hex.slice(10).join("")}`;
    }

    function setMessage(element, text) {
        if (element) element.textContent = text || "";
    }

    window.addEventListener("pagehide", () => {
        if (cardBrickController?.unmount) cardBrickController.unmount();
        cardBrickController = null;
    });
    window.BoostPayments = { initPayments };
}());
