document.addEventListener("DOMContentLoaded", () => {
    document.body.classList.add("is-ready");

    if (window.lucide) {
        window.lucide.createIcons({
            attrs: {
                "stroke-width": 1.8
            }
        });
    }

    const topbar = document.querySelector(".topbar");
    const updateTopbar = () => {
        if (!topbar) return;
        topbar.classList.toggle("is-scrolled", window.scrollY > 12);
    };
    updateTopbar();
    window.addEventListener("scroll", updateTopbar, { passive: true });

    const revealElements = document.querySelectorAll(".reveal");
    if ("IntersectionObserver" in window) {
        const revealObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach((entry) => {
                if (!entry.isIntersecting) return;
                entry.target.classList.add("is-visible");
                observer.unobserve(entry.target);
            });
        }, {
            threshold: .01,
            rootMargin: "0px 0px -4% 0px"
        });

        revealElements.forEach((element, index) => {
            element.style.setProperty("--reveal-delay", `${Math.min(index * 78, 320)}ms`);
            revealObserver.observe(element);
        });
    } else {
        revealElements.forEach((element, index) => {
            element.style.setProperty("--reveal-delay", `${Math.min(index * 78, 320)}ms`);
            element.classList.add("is-visible");
        });
    }

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
                const item = document.createElement("li");
                item.className = "file-preview";
                item.style.animationDelay = `${index * 70}ms`;
                item.innerHTML = `
                    <span class="file-icon"><i data-lucide="file"></i></span>
                    <span class="file-name"></span>
                    <span class="file-size">${formatBytes(file.size)}</span>
                `;
                item.querySelector(".file-name").textContent = file.name;
                list.appendChild(item);
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

    document.querySelectorAll("form[data-loading-form]").forEach((form) => {
        form.addEventListener("submit", () => {
            const button = form.querySelector('button[type="submit"]');
            if (!button) return;
            button.classList.add("is-loading");
            button.setAttribute("aria-busy", "true");
        });
    });

    const authContainer = document.getElementById("auth-container");
    const registerButton = document.getElementById("register");
    const loginButton = document.getElementById("login");

    if (authContainer && registerButton && loginButton) {
        registerButton.addEventListener("click", () => {
            authContainer.classList.add("active");
            history.replaceState(null, "", "/registrar");
        });

        loginButton.addEventListener("click", () => {
            authContainer.classList.remove("active");
            history.replaceState(null, "", "/login");
        });
    }

    document.querySelectorAll('a[href]').forEach((link) => {
        link.addEventListener("click", (event) => {
            const url = new URL(link.href, window.location.href);
            const isModifiedClick = event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0;
            const isSameOrigin = url.origin === window.location.origin;
            const isHashOnly = url.pathname === window.location.pathname && url.hash;
            const isDownload = url.pathname.includes("/download");
            const skipsTransition = link.target || link.hasAttribute("download") || link.closest("[data-no-page-transition]");

            if (isModifiedClick || !isSameOrigin || isHashOnly || isDownload || skipsTransition) return;

            event.preventDefault();
            document.body.classList.add("is-leaving");
            window.setTimeout(() => {
                window.location.href = url.href;
            }, 260);
        });
    });
});

function formatBytes(bytes) {
    if (!bytes) return "0 KB";
    const units = ["B", "KB", "MB", "GB"];
    const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    return `${(bytes / Math.pow(1024, index)).toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}
