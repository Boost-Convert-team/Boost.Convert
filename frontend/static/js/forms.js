(function () {
    function initUploadZones() {
        document.querySelectorAll(".upload-zone").forEach((zone) => {
            const input = zone.querySelector('input[type="file"]');
            const list = zone.querySelector(".file-preview-list");
            const note = zone.querySelector(".upload-note");

            if (!input || !list) return;

            const renderFiles = () => {
                list.innerHTML = "";
                const files = Array.from(input.files || []).slice(0, 6);
                zone.classList.toggle("has-files", files.length > 0);

                files.forEach((file, index) => {
                    list.appendChild(createFilePreview(file, index));
                });

                if (note && input.files.length) {
                    note.textContent = `${input.files.length} arquivo(s) pronto(s) para converter`;
                }

                if (window.lucide) window.lucide.createIcons();
            };

            ["dragenter", "dragover"].forEach((eventName) => {
                zone.addEventListener(eventName, (event) => {
                    event.preventDefault();
                    zone.classList.add("is-dragging");
                });
            });

            ["dragleave", "drop"].forEach((eventName) => {
                zone.addEventListener(eventName, (event) => {
                    event.preventDefault();
                    zone.classList.remove("is-dragging");
                });
            });

            zone.addEventListener("drop", (event) => {
                if (event.dataTransfer.files.length) {
                    input.files = event.dataTransfer.files;
                    renderFiles();
                }
            });

            input.addEventListener("change", renderFiles);
        });
    }

    function createFilePreview(file, index) {
        const item = document.createElement("li");
        item.className = "file-preview";
        item.style.animationDelay = `${index * 70}ms`;
        item.innerHTML = `
            <span class="file-icon"><i data-lucide="file"></i></span>
            <span class="file-name"></span>
            <span class="file-size">${window.BoostUtils.formatBytes(file.size)}</span>
        `;
        item.querySelector(".file-name").textContent = file.name;
        return item;
    }

    function initLoadingForms() {
        document.querySelectorAll("form[data-loading-form]").forEach((form) => {
            form.addEventListener("submit", () => {
                const button = form.querySelector('button[type="submit"]');
                if (!button) return;
                button.classList.add("is-loading");
                button.setAttribute("aria-busy", "true");
            });
        });
    }

    function initHeroUpload() {
        const form = document.querySelector("[data-hero-upload-form]");
        if (!form) return;

        const input = form.querySelector("#hero-upload-file");
        const dropzone = form.querySelector(".hero-upload-dropzone");
        const selectedFile = form.querySelector("[data-hero-selected-file]");
        const panel = form.querySelector("[data-hero-conversion-panel]");
        const optionsList = form.querySelector("[data-hero-conversion-options]");
        const message = form.querySelector("[data-hero-upload-message]");
        let selectedRoute = "";

        if (!input || !dropzone || !panel || !optionsList) return;

        const setMessage = (text) => {
            if (!message) return;
            message.textContent = text || "";
        };

        const setSelectedFile = (file) => {
            if (!selectedFile) return;
            if (!file) {
                selectedFile.hidden = true;
                selectedFile.textContent = "";
                return;
            }

            selectedFile.hidden = false;
            selectedFile.textContent = `${file.name} - ${window.BoostUtils.formatBytes(file.size)}`;
        };

        const resetOptions = () => {
            selectedRoute = "";
            form.removeAttribute("action");
            form.classList.remove("has-conversions");
            panel.hidden = true;
            optionsList.innerHTML = "";
        };

        const renderOptions = (tools) => {
            resetOptions();

            if (!tools.length) {
                setMessage("Nenhuma conversao disponivel para este formato.");
                return;
            }

            form.classList.add("has-conversions");
            panel.hidden = false;
            optionsList.innerHTML = "";

            tools.forEach((tool) => {
                const button = document.createElement("button");
                button.className = "hero-upload-output-option";
                button.type = "submit";
                button.dataset.route = tool.route;
                button.innerHTML = `
                    <span>${tool.output || tool.name}</span>
                    <small>${tool.name}</small>
                `;
                button.addEventListener("click", () => {
                    selectedRoute = tool.route;
                    form.action = tool.route;
                });
                optionsList.appendChild(button);
            });

            setMessage("Escolha uma saida para converter agora.");
        };

        const getFileExtension = (file) => {
            const name = file?.name || "";
            const dotIndex = name.lastIndexOf(".");
            if (dotIndex < 0) return "";
            return name.slice(dotIndex + 1).toLowerCase();
        };

        const loadConversions = async () => {
            const file = input.files?.[0];
            resetOptions();
            setSelectedFile(file);

            if (!file) {
                setMessage("");
                return;
            }

            const extension = getFileExtension(file);
            if (!extension) {
                setMessage("Nao consegui identificar o formato do arquivo.");
                return;
            }

            setMessage("Buscando conversoes disponiveis...");

            try {
                const response = await fetch(`/api/conversion-options?extension=${encodeURIComponent(extension)}`);
                if (!response.ok) throw new Error("Erro ao buscar conversoes.");
                const data = await response.json();
                renderOptions(data.tools || []);
            } catch {
                resetOptions();
                setMessage("Nao foi possivel carregar as conversoes agora.");
            }
        };

        ["dragenter", "dragover"].forEach((eventName) => {
            dropzone.addEventListener(eventName, (event) => {
                event.preventDefault();
                dropzone.classList.add("is-dragging");
            });
        });

        ["dragleave", "drop"].forEach((eventName) => {
            dropzone.addEventListener(eventName, (event) => {
                event.preventDefault();
                dropzone.classList.remove("is-dragging");
            });
        });

        dropzone.addEventListener("drop", (event) => {
            const file = event.dataTransfer.files?.[0];
            if (!file) return;

            const transfer = new DataTransfer();
            transfer.items.add(file);
            input.files = transfer.files;
            loadConversions();
        });

        input.addEventListener("change", loadConversions);

        form.addEventListener("submit", (event) => {
            if (!input.files?.length) {
                event.preventDefault();
                setMessage("Selecione um arquivo primeiro.");
                return;
            }

            if (!selectedRoute) {
                event.preventDefault();
                setMessage("Escolha uma saida antes de converter.");
                return;
            }

            form.action = selectedRoute;
            form.classList.add("is-submitting");
        });
    }

    function initAuthToggle() {
        const authContainer = document.getElementById("auth-container");
        const registerButton = document.getElementById("register");
        const loginButton = document.getElementById("login");

        if (!authContainer || !registerButton || !loginButton) return;

        registerButton.addEventListener("click", () => {
            authContainer.classList.add("active");
            history.replaceState(null, "", "/registrar");
        });

        loginButton.addEventListener("click", () => {
            authContainer.classList.remove("active");
            history.replaceState(null, "", "/login");
        });
    }

    window.BoostForms = {
        initHeroUpload,
        initAuthToggle,
        initLoadingForms,
        initUploadZones
    };
})();
