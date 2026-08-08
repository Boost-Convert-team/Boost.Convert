(function () {
    let cardBrickController = null;
    let cardBrickInitializing = false;
    let cardBrickReady = false;
    let cardBrickInitializationFailed = false;
    let cardSubmissionInFlight = false;

    function initPayments() {
        initCardPaymentBrick();
        initPixCreationForm();
        initPixCopyButton();
        initCardPaymentStatusPolling();
        initPixPaymentStatusPolling();
    }

    async function initCardPaymentBrick() {
        const config = document.querySelector("[data-card-payment-config]");
        const container = document.getElementById("cardPaymentBrick_container");
        if (!config || !container) return;
        if (cardBrickController || cardBrickInitializing) return;
        const message = document.querySelector("[data-card-payment-message]");
        const publicKey = String(config.dataset.publicKey || "").trim();
        if (!publicKey) {
            setMessage(message, "O pagamento por cartão está temporariamente indisponível.");
            return;
        }
        if (!window.MercadoPago) {
            setMessage(message, "Não foi possível carregar o pagamento seguro por cartão.");
            return;
        }

        cardBrickInitializing = true;
        cardBrickReady = false;
        cardBrickInitializationFailed = false;
        let idempotencyKey = config.dataset.idempotencyKey;
        try {
            const amount = Number(config.dataset.amount);
            if (!Number.isFinite(amount) || amount <= 0) {
                throw new Error("Valor de pagamento inválido.");
            }
            const mercadoPago = new window.MercadoPago(publicKey, { locale: "pt-BR" });
            const bricksBuilder = mercadoPago.bricks();
            const controller = await bricksBuilder.create("cardPayment", container.id, {
                initialization: {
                    amount,
                    payer: { email: config.dataset.payerEmail }
                },
                customization: {
                    visual: { style: { theme: "default" } },
                    paymentMethods: {
                        types: { included: ["credit_card", "debit_card"] },
                        maxInstallments: Number(config.dataset.maxInstallments || 12)
                    }
                },
                callbacks: {
                    onReady: () => {
                        cardBrickReady = true;
                        container.dataset.brickReady = "true";
                        setMessage(message, "");
                    },
                    onSubmit: async (formData, additionalData) => {
                        if (cardSubmissionInFlight) return;
                        cardSubmissionInFlight = true;
                        let redirecting = false;
                        setMessage(message, "Processando pagamento com segurança...");
                        try {
                            const payload = buildCardPayload(formData, additionalData);
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
                    onError: (error) => {
                        reportCardPaymentError("sdk", error);
                        if (!cardBrickReady) {
                            cardBrickInitializationFailed = true;
                            if (cardBrickController?.unmount) cardBrickController.unmount();
                            cardBrickController = null;
                            setMessage(message, "Não foi possível iniciar o pagamento seguro por cartão.");
                        } else if (!message?.textContent) {
                            setMessage(message, "Não foi possível processar o cartão. Revise os dados e tente novamente.");
                        }
                    }
                }
            });
            if (cardBrickInitializationFailed) {
                if (controller?.unmount) controller.unmount();
            } else {
                cardBrickController = controller;
            }
        } catch (error) {
            reportCardPaymentError("initialization", error);
            setMessage(message, "Não foi possível iniciar o pagamento seguro por cartão.");
        } finally {
            cardBrickInitializing = false;
        }
    }

    function buildCardPayload(formData, additionalData) {
        const payer = formData && typeof formData.payer === "object" ? formData.payer : {};
        const payload = {
            token: String(formData?.token || ""),
            payment_method_id: String(formData?.payment_method_id || ""),
            payment_type_id: String(additionalData?.paymentTypeId || ""),
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

    function initCardPaymentStatusPolling() {
        const page = document.querySelector("[data-card-status-page]");
        const status = page?.querySelector("[data-card-payment-status]");
        if (!page || !status || !page.dataset.statusUrl) return;
        if (page.dataset.paymentPollingInitialized === "true") return;
        page.dataset.paymentPollingInitialized = "true";
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

    function initPixCreationForm() {
        const form = document.querySelector("[data-pix-payment-form]");
        if (!form || form.dataset.paymentInitialized === "true") return;
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
                if (!payload.redirect_url) throw new Error("Pagamento criado sem página de destino.");
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
        if (!button || !field || button.dataset.copyInitialized === "true") return;
        button.dataset.copyInitialized = "true";
        button.addEventListener("click", async () => {
            try {
                await navigator.clipboard.writeText(field.value);
            } catch (_) {
                field.focus();
                field.select();
                document.execCommand("copy");
            }
            button.textContent = "Código Pix copiado";
        });
    }

    function initPixPaymentStatusPolling() {
        const page = document.querySelector("[data-pix-status-page]");
        const status = page?.querySelector("[data-pix-payment-status]");
        if (!page || !status || !page.dataset.statusUrl) return;
        if (page.dataset.paymentPollingInitialized === "true") return;
        page.dataset.paymentPollingInitialized = "true";
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
                } else if (["rejected", "cancelled", "canceled", "expired"].includes(payload.status)) {
                    window.clearInterval(interval);
                    status.textContent = "O pagamento Pix não foi aprovado ou expirou.";
                }
            } catch (_) {
                return;
            }
        }, 3000);
    }

    function renderApprovedStatus(page, status) {
        status.dataset.status = "approved";
        status.textContent = "Pagamento confirmado. Seu BoostConvert PRO está ativo.";
        const accountLink = page.querySelector(
            "[data-card-account-link], [data-pix-account-link]"
        );
        if (accountLink) accountLink.hidden = false;
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

    function setMessage(message, text) {
        if (message) message.textContent = text || "";
    }

    function setButtonLoading(button, loading) {
        if (!button) return;
        button.disabled = loading;
        button.setAttribute("aria-busy", String(loading));
    }

    function reportCardPaymentError(stage, error) {
        const name = String(error?.name || "Error");
        const detail = String(error?.message || error || "Falha desconhecida.");
        console.error(`[BoostPayments] card ${stage}: ${name}: ${detail}`);
    }

    window.addEventListener("pagehide", () => {
        if (cardBrickController?.unmount) cardBrickController.unmount();
        cardBrickController = null;
        cardBrickReady = false;
    });
    window.BoostPayments = { initPayments };
})();
