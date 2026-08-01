(function () {
    let cardBrickController = null;
    let cardBrickInitializing = false;
    let cardSubmissionInFlight = false;

    function initPayments() {
        initCardPaymentBrick();
        initPixCreationForm();
        initPixCopyButton();
        initPaymentStatusPolling("[data-pix-status-page]", "[data-pix-payment-status]", "[data-pix-account-link]");
        initPaymentStatusPolling("[data-card-status-page]", "[data-card-payment-status]", "[data-card-account-link]");
    }

    async function initCardPaymentBrick() {
        const config = document.querySelector("[data-card-payment-config]");
        const container = document.getElementById("cardPaymentBrick_container");
        if (!config || !container) return;
        if (cardBrickController || cardBrickInitializing) return;
        const message = document.querySelector("[data-card-payment-message]");
        if (!window.MercadoPago) {
            setMessage(message, "Não foi possível carregar o pagamento seguro por cartão.");
            return;
        }

        cardBrickInitializing = true;
        let idempotencyKey = config.dataset.idempotencyKey;
        try {
            const amount = Number(config.dataset.amount);
            if (!Number.isFinite(amount) || amount <= 0) {
                throw new Error("Valor de pagamento inválido.");
            }
            const mercadoPago = new window.MercadoPago(config.dataset.publicKey, { locale: "pt-BR" });
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
                    onReady: () => {
                        container.dataset.brickReady = "true";
                        setMessage(message, "");
                    },
                    onSubmit: async (formData) => {
                        if (cardSubmissionInFlight) return;
                        cardSubmissionInFlight = true;
                        let redirecting = false;
                        setMessage(message, "Processando pagamento com segurança...");
                        try {
                            const payload = buildCardPayload(formData);
                            const response = await fetch(config.dataset.endpoint, {
                                method: "POST",
                                headers: {
                                    Accept: "application/json",
                                    "Content-Type": "application/json",
                                    "X-CSRF-Token": config.dataset.csrfToken,
                                    "X-Idempotency-Key": idempotencyKey
                                },
                                credentials: "same-origin",
                                body: JSON.stringify(payload)
                            });
                            const result = await readJson(response);
                            if (!response.ok) {
                                if (result.status === "rejected") idempotencyKey = createUuid();
                                const errorMessage = result.error || "Não foi possível processar o cartão.";
                                setMessage(message, errorMessage);
                                throw new Error(errorMessage);
                            }
                            if (!result.redirect_url) throw new Error("Pagamento criado sem página de status.");
                            redirecting = true;
                            window.location.assign(result.redirect_url);
                        } finally {
                            if (!redirecting) cardSubmissionInFlight = false;
                        }
                    },
                    onError: () => {
                        if (!message?.textContent) {
                            setMessage(message, "Não foi possível processar o cartão. Revise os dados e tente novamente.");
                        }
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
            payer: { email: String(payer.email || "") }
        };
        if (payer.identification && payer.identification.type && payer.identification.number) {
            payload.payer.identification = {
                type: String(payer.identification.type),
                number: String(payer.identification.number)
            };
        }
        return payload;
    }

    function initPixCreationForm() {
        const form = document.querySelector("[data-pix-payment-form]");
        if (!form) return;
        if (form.dataset.paymentInitialized === "true") return;
        form.dataset.paymentInitialized = "true";
        const button = form.querySelector('button[type="submit"]');
        const message = form.querySelector("[data-pix-payment-message]");

        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            if (form.dataset.submissionInFlight === "true") return;
            form.dataset.submissionInFlight = "true";
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
                form.dataset.submissionInFlight = "false";
                setButtonLoading(button, false);
            }
        });
    }

    function initPixCopyButton() {
        const button = document.querySelector("[data-copy-pix-code]");
        const field = document.querySelector("[data-pix-copy-code]");
        if (!button || !field) return;
        if (button.dataset.copyInitialized === "true") return;
        button.dataset.copyInitialized = "true";
        button.addEventListener("click", async () => {
            const copied = await copyText(field.value, field);
            if (!copied) return;
            const originalHtml = button.innerHTML;
            button.textContent = "Código Pix copiado";
            window.setTimeout(() => { button.innerHTML = originalHtml; }, 2200);
        });
    }

    function initPaymentStatusPolling(pageSelector, statusSelector, accountSelector) {
        const page = document.querySelector(pageSelector);
        const status = page?.querySelector(statusSelector);
        if (!page || !status || !page.dataset.statusUrl) return;
        if (page.dataset.paymentPollingInitialized === "true") return;
        page.dataset.paymentPollingInitialized = "true";
        if (page.dataset.paymentConfirmed === "true") {
            renderApprovedStatus(page, status, accountSelector);
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
                    renderApprovedStatus(page, status, accountSelector);
                } else if (["rejected", "cancelled", "canceled", "expired", "refunded", "charged_back"].includes(payload.status)) {
                    window.clearInterval(interval);
                    status.dataset.status = payload.status;
                    status.textContent = "O pagamento não foi aprovado ou deixou de ser válido.";
                }
            } catch (_) {
                return;
            }
        }, 3000);
    }

    function renderApprovedStatus(page, status, accountSelector) {
        status.dataset.status = "approved";
        status.textContent = "Pagamento confirmado. Seu BoostConvert PRO está ativo.";
        const accountLink = page.querySelector(accountSelector);
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

    function createUuid() {
        if (window.crypto?.randomUUID) return window.crypto.randomUUID();
        const bytes = new Uint8Array(16);
        window.crypto.getRandomValues(bytes);
        bytes[6] = (bytes[6] & 0x0f) | 0x40;
        bytes[8] = (bytes[8] & 0x3f) | 0x80;
        const hex = Array.from(bytes, (value) => value.toString(16).padStart(2, "0"));
        return `${hex.slice(0, 4).join("")}-${hex.slice(4, 6).join("")}-${hex.slice(6, 8).join("")}-${hex.slice(8, 10).join("")}-${hex.slice(10).join("")}`;
    }

    function setButtonLoading(button, loading) {
        if (!button) return;
        button.disabled = loading;
        button.setAttribute("aria-busy", String(loading));
    }

    function setMessage(message, text) {
        if (message) message.textContent = text || "";
    }

    window.addEventListener("pagehide", () => {
        if (cardBrickController?.unmount) cardBrickController.unmount();
        cardBrickController = null;
    });
    window.BoostPayments = { initPayments };
})();
