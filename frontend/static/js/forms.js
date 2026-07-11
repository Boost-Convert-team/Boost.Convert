(function () {
    function initUploadZones() {
        document.querySelectorAll(".upload-zone").forEach(initUploadZone);
    }

    function initUploadZone(zone) {
        const input = zone.querySelector('input[type="file"]');
        const list = zone.querySelector(".file-preview-list");
        const note = zone.querySelector(".upload-note");
        const addButton = zone.querySelector("[data-upload-add-button]");

        if (!input || !list) return;

        if (note) note.dataset.defaultText = note.textContent;

        const defaultAccept = input.getAttribute("accept") || "";
        const state = { files: Array.from(input.files || []), validationMessage: "" };
        const render = () => renderUploadFiles(zone, list, note, state.files, state.validationMessage);
        const acceptFiles = (files) => {
            const result = getSameExtensionFiles(state.files, files, input.multiple);
            state.files = result.files;
            state.validationMessage = result.message;
            if (!syncUploadInput(input, state.files)) state.files = Array.from(input.files || []);
            restoreInputAccept(input, defaultAccept);
            render();
        };

        addUploadDragEvents(zone, acceptFiles);
        input.addEventListener("change", () => acceptFiles(input.files));
        if (addButton) addButton.addEventListener("click", (event) => {
            restrictInputToFirstExtension(input, state.files);
            openUploadPicker(event, input);
        });
        input.addEventListener("cancel", () => restoreInputAccept(input, defaultAccept));
        render();
    }

    function renderUploadFiles(zone, list, note, files, validationMessage = "") {
        list.innerHTML = "";
        zone.classList.toggle("has-files", files.length > 0);
        files.slice(0, 6).forEach((file, index) => list.appendChild(createFilePreview(file, index)));
        renderUploadNote(note, files.length, validationMessage);
        if (window.lucide) window.lucide.createIcons();
    }

    function renderUploadNote(note, fileCount, validationMessage = "") {
        if (!note) return;

        if (validationMessage) {
            note.textContent = validationMessage;
            return;
        }

        note.textContent = fileCount
            ? `${fileCount} arquivo(s) pronto(s) para converter`
            : note.dataset.defaultText || "";
    }

    function getSameExtensionFiles(currentFiles, files, allowsMultiple = true) {
        const existingFiles = Array.from(currentFiles || []);
        const incomingFiles = Array.from(files || []);
        if (!incomingFiles.length) return { files: existingFiles, message: "" };
        if (!allowsMultiple) return { files: incomingFiles.slice(0, 1), message: "" };

        const requiredExtension = getFileExtension(existingFiles[0] || incomingFiles[0]);
        if (!requiredExtension) {
            return { files: existingFiles, message: "Nao foi possivel identificar a extensao do arquivo." };
        }

        const acceptedFiles = incomingFiles.filter((file) => getFileExtension(file) === requiredExtension);
        const rejectedCount = incomingFiles.length - acceptedFiles.length;
        return {
            files: existingFiles.concat(acceptedFiles),
            message: rejectedCount
                ? `Adicione apenas arquivos .${requiredExtension.toUpperCase()}. ${rejectedCount} arquivo(s) ignorado(s).`
                : ""
        };
    }

    function getFileExtension(file) {
        const name = String(file?.name || "");
        const dotIndex = name.lastIndexOf(".");
        if (dotIndex < 0 || dotIndex === name.length - 1) return "";
        return name.slice(dotIndex + 1).toLowerCase();
    }

    function restrictInputToFirstExtension(input, files) {
        const extension = getFileExtension(Array.from(files || [])[0]);
        if (extension) input.setAttribute("accept", `.${extension}`);
    }

    function restoreInputAccept(input, defaultAccept) {
        if (defaultAccept) {
            input.setAttribute("accept", defaultAccept);
            return;
        }
        input.removeAttribute("accept");
    }

    function syncUploadInput(input, files) {
        if (typeof DataTransfer === "undefined") return false;

        try {
            const transfer = new DataTransfer();
            files.forEach((file) => transfer.items.add(file));
            input.files = transfer.files;
            return true;
        } catch {
            return false;
        }
    }

    function addUploadDragEvents(zone, acceptFiles) {
        addUploadStateEvents(zone, ["dragenter", "dragover"], true);
        addUploadStateEvents(zone, ["dragleave", "drop"], false);
        zone.addEventListener("drop", (event) => {
            const files = event.dataTransfer?.files;
            if (files?.length) acceptFiles(files);
        });
    }

    function addUploadStateEvents(zone, eventNames, isDragging) {
        eventNames.forEach((eventName) => {
            zone.addEventListener(eventName, (event) => {
                event.preventDefault();
                zone.classList.toggle("is-dragging", isDragging);
            });
        });
    }

    function openUploadPicker(event, input) {
        event.preventDefault();
        event.stopPropagation();
        input.click();
    }

    function createFilePreview(file, index) {
        const item = document.createElement("li");
        item.className = "file-preview";
        item.style.animationDelay = `${index * 70}ms`;
        const icon = document.createElement("span");
        icon.className = "file-icon";
        const iconGlyph = document.createElement("i");
        iconGlyph.setAttribute("data-lucide", "file");
        icon.appendChild(iconGlyph);

        const name = document.createElement("span");
        name.className = "file-name file-name-safe";
        name.textContent = file.name;

        const size = document.createElement("span");
        size.className = "file-size";
        size.textContent = window.BoostUtils.formatBytes(file.size);

        item.append(icon, name, size);
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

    function initProCheckoutForms() {
        document.querySelectorAll("[data-pro-checkout-form]").forEach((form) => {
            form.addEventListener("submit", handleProCheckoutSubmit);
        });
    }

    async function handleProCheckoutSubmit(event) {
        event.preventDefault();

        const form = event.currentTarget;
        const button = form.querySelector('button[type="submit"]');
        const message = form.querySelector("[data-pro-checkout-message]");

        setProCheckoutMessage(message, "");
        setProCheckoutLoading(button, true);

        try {
            const response = await fetch(form.action, {
                method: "POST",
                body: new FormData(form),
                headers: { Accept: "application/json" },
                credentials: "same-origin"
            });

            if (response.redirected) {
                window.location.assign(response.url);
                return;
            }

            const payload = await readCheckoutResponse(response);
            if (!response.ok) {
                throw new Error(payload.error || "Nao foi possivel iniciar o pagamento.");
            }

            if (payload.checkout_url) {
                window.location.assign(payload.checkout_url);
                return;
            }

            throw new Error(payload.error || "Mercado Pago nao retornou a URL do checkout.");
        } catch (error) {
            setProCheckoutLoading(button, false);
            setProCheckoutMessage(message, error.message || "Nao foi possivel iniciar o pagamento.");
        } finally {
            setProCheckoutLoading(button, false);
        }
    }

    async function readCheckoutResponse(response) {
        const contentType = response.headers.get("content-type") || "";
        if (!contentType.includes("application/json")) return {};
        return response.json();
    }

    function setProCheckoutLoading(button, isLoading) {
        if (!button) return;
        button.disabled = isLoading;
        button.classList.toggle("is-loading", isLoading);
        button.setAttribute("aria-busy", String(isLoading));
    }

    function setProCheckoutMessage(message, text, state) {
        if (!message) return;
        message.textContent = text || "";
        message.dataset.state = state || "";
    }

    function initHeroUpload() {
        const form = document.querySelector("[data-hero-upload-form]");
        if (!form) return;

        const input = form.querySelector("#hero-upload-file");
        const dropzone = form.querySelector(".hero-upload-dropzone");
        const selectedFile = form.querySelector("[data-hero-selected-file]");
        const uploadTitle = form.querySelector("[data-hero-upload-title]");
        const uploadButtonLabel = form.querySelector("[data-hero-upload-button-label]");
        const addFilesButton = form.querySelector("[data-hero-add-files]");
        const uploadLimit = form.querySelector("[data-hero-upload-limit]");
        const panel = form.querySelector("[data-hero-conversion-panel]");
        const optionsList = form.querySelector("[data-hero-conversion-options]");
        const message = form.querySelector("[data-hero-upload-message]");
        const defaultHeroAccept = input?.getAttribute("accept") || "";

        if (!input || !dropzone || !panel || !optionsList) return;

        let heroFiles = Array.from(input.files || []);
        let shouldAppendHeroFiles = false;
        let selectedRoute = "";

        const setMessage = (text) => {
            if (!message) return;
            message.textContent = text || "";
        };

        const setSelectedFiles = (files) => {
            if (!selectedFile) return;
            const fileList = Array.from(files || []);
            const hasFiles = fileList.length > 0;
            form.classList.toggle("has-file", hasFiles);
            if (addFilesButton) addFilesButton.hidden = !hasFiles;
            if (uploadLimit) uploadLimit.hidden = hasFiles;
            if (!fileList.length) {
                selectedFile.hidden = true;
                selectedFile.textContent = "";
                selectedFile.removeAttribute("title");
                if (uploadTitle) uploadTitle.textContent = "Arraste seu arquivo aqui";
                if (uploadButtonLabel) uploadButtonLabel.textContent = "Selecionar arquivo";
                return;
            }

            const totalSize = fileList.reduce((sum, currentFile) => sum + currentFile.size, 0);
            const firstFile = fileList[0];
            selectedFile.hidden = false;
            selectedFile.textContent = fileList.length === 1
                ? `${firstFile.name} - ${window.BoostUtils.formatBytes(firstFile.size)}`
                : `${fileList.length} arquivos selecionados - ${window.BoostUtils.formatBytes(totalSize)}`;
            selectedFile.title = fileList.map((currentFile) => currentFile.name).join(", ");
            if (uploadTitle) uploadTitle.textContent = "Arquivo pronto para converter";
            if (uploadButtonLabel) uploadButtonLabel.textContent = "Trocar arquivo";
        };

        const syncHeroInput = (files) => {
            if (typeof DataTransfer === "undefined") return false;

            try {
                const transfer = new DataTransfer();
                files.forEach((file) => transfer.items.add(file));
                input.files = transfer.files;
                return true;
            } catch {
                return false;
            }
        };

        const setHeroFiles = (files, shouldAppend = false) => {
            const baseFiles = shouldAppend ? heroFiles : [];
            const result = getSameExtensionFiles(baseFiles, files, true);
            heroFiles = result.files;
            if (!syncHeroInput(heroFiles)) heroFiles = Array.from(input.files || []);
            restoreInputAccept(input, defaultHeroAccept);
            return result.message;
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
                const output = document.createElement("span");
                output.textContent = tool.output || tool.name;
                const name = document.createElement("small");
                name.textContent = tool.name;
                button.append(output, name);
                button.addEventListener("click", () => {
                    selectedRoute = tool.route;
                    form.action = tool.route;
                });
                optionsList.appendChild(button);
            });

            setMessage("Escolha uma saida para converter agora.");
        };

        const loadConversions = async (validationMessage = "") => {
            const file = heroFiles[0];
            resetOptions();
            setSelectedFiles(heroFiles);

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
                if (validationMessage) setMessage(validationMessage);
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
            const files = event.dataTransfer.files;
            if (!files?.length) return;

            const validationMessage = setHeroFiles(files, true);
            loadConversions(validationMessage);
        });

        input.addEventListener("change", () => {
            const validationMessage = setHeroFiles(input.files, shouldAppendHeroFiles);
            shouldAppendHeroFiles = false;
            loadConversions(validationMessage);
        });
        input.addEventListener("cancel", () => {
            shouldAppendHeroFiles = false;
            restoreInputAccept(input, defaultHeroAccept);
        });

        if (addFilesButton) {
            addFilesButton.addEventListener("click", (event) => {
                event.preventDefault();
                event.stopPropagation();
                shouldAppendHeroFiles = true;
                restrictInputToFirstExtension(input, heroFiles);
                input.click();
            });
            addFilesButton.addEventListener("keydown", (event) => {
                if (event.key !== "Enter" && event.key !== " ") return;
                event.preventDefault();
                event.stopPropagation();
                shouldAppendHeroFiles = true;
                restrictInputToFirstExtension(input, heroFiles);
                input.click();
            });
        }

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
        initProCheckoutForms,
        initUploadZones,
        getFileExtension,
        getSameExtensionFiles
    };
})();
