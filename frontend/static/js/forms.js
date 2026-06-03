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
        initAuthToggle,
        initLoadingForms,
        initUploadZones
    };
})();
