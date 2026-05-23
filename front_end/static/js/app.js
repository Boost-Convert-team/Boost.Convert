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

    const megaDropdown = document.querySelector(".mega-dropdown");
    if (megaDropdown) {
        const megaMenu = megaDropdown.querySelector(".mega-menu");
        let megaCloseTimer;

        const openMegaMenu = () => {
            window.clearTimeout(megaCloseTimer);
            megaDropdown.classList.add("is-open");
        };

        const closeMegaMenu = () => {
            window.clearTimeout(megaCloseTimer);
            megaCloseTimer = window.setTimeout(() => {
                megaDropdown.classList.remove("is-open");
            }, 260);
        };

        megaDropdown.addEventListener("pointerenter", openMegaMenu);
        megaDropdown.addEventListener("pointerleave", closeMegaMenu);
        megaDropdown.addEventListener("focusin", openMegaMenu);
        megaDropdown.addEventListener("focusout", (event) => {
            if (!megaDropdown.contains(event.relatedTarget)) closeMegaMenu();
        });

        if (megaMenu) {
            megaMenu.addEventListener("pointerenter", openMegaMenu);
            megaMenu.addEventListener("pointerleave", closeMegaMenu);
        }
    }

    const searchForm = document.querySelector("[data-tool-search]");
    const searchInput = searchForm?.querySelector("[data-tool-search-input]");
    const searchResults = searchForm?.querySelector("[data-tool-search-results]");
    const searchDataElement = document.getElementById("tool-search-data");

    if (searchForm && searchInput && searchResults && searchDataElement) {
        const toolSearchIndex = parseToolSearchIndex(searchDataElement);
        let activeSearchIndex = 0;
        let currentSearchResults = [];

        const closeToolSearch = () => {
            searchForm.classList.remove("is-open");
            searchResults.innerHTML = "";
            currentSearchResults = [];
            activeSearchIndex = 0;
        };

        const openToolSearch = () => {
            if (currentSearchResults.length || searchInput.value.trim()) {
                searchForm.classList.add("is-open");
            }
        };

        const setActiveSearchResult = (index) => {
            activeSearchIndex = Math.max(0, Math.min(index, currentSearchResults.length - 1));
            searchResults.querySelectorAll(".tool-search-result").forEach((item, itemIndex) => {
                item.classList.toggle("is-active", itemIndex === activeSearchIndex);
                item.setAttribute("aria-selected", itemIndex === activeSearchIndex ? "true" : "false");
            });
        };

        const renderToolSearch = () => {
            const query = searchInput.value.trim();
            searchResults.innerHTML = "";

            if (!query) {
                closeToolSearch();
                return;
            }

            currentSearchResults = getToolSearchMatches(toolSearchIndex, query).slice(0, 7);

            if (!currentSearchResults.length) {
                const empty = document.createElement("div");
                empty.className = "tool-search-empty";
                empty.textContent = "Nenhuma ferramenta encontrada";
                searchResults.appendChild(empty);
                searchForm.classList.add("is-open");
                return;
            }

            currentSearchResults.forEach((entry, index) => {
                const link = document.createElement("a");
                link.className = "tool-search-result";
                link.href = entry.url;
                link.setAttribute("role", "option");
                link.setAttribute("aria-selected", index === activeSearchIndex ? "true" : "false");
                if (index === activeSearchIndex) link.classList.add("is-active");

                const icon = document.createElement("span");
                icon.className = "tool-search-icon";
                const iconGlyph = document.createElement("i");
                iconGlyph.setAttribute("data-lucide", entry.icon || "file");
                iconGlyph.setAttribute("aria-hidden", "true");
                icon.appendChild(iconGlyph);

                const copy = document.createElement("span");
                const title = document.createElement("strong");
                title.textContent = entry.label;
                const category = document.createElement("small");
                category.textContent = entry.category;
                copy.append(title, category);

                const chip = document.createElement("span");
                chip.className = "tool-search-chip";
                chip.textContent = entry.category;

                link.append(icon, copy, chip);
                link.addEventListener("mouseenter", () => setActiveSearchResult(index));
                searchResults.appendChild(link);
            });

            searchForm.classList.add("is-open");
            if (window.lucide) window.lucide.createIcons();
        };

        searchInput.addEventListener("input", () => {
            activeSearchIndex = 0;
            renderToolSearch();
        });

        searchInput.addEventListener("focus", openToolSearch);

        searchInput.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                closeToolSearch();
                searchInput.blur();
                return;
            }

            if (!currentSearchResults.length) return;

            if (event.key === "ArrowDown") {
                event.preventDefault();
                setActiveSearchResult(activeSearchIndex + 1);
            }

            if (event.key === "ArrowUp") {
                event.preventDefault();
                setActiveSearchResult(activeSearchIndex - 1);
            }

            if (event.key === "Enter") {
                event.preventDefault();
                window.location.href = currentSearchResults[activeSearchIndex]?.url || currentSearchResults[0].url;
            }
        });

        searchForm.addEventListener("submit", (event) => {
            event.preventDefault();
            const firstResult = currentSearchResults[activeSearchIndex] || currentSearchResults[0];
            if (firstResult) window.location.href = firstResult.url;
        });

        document.addEventListener("pointerdown", (event) => {
            if (!searchForm.contains(event.target)) closeToolSearch();
        });
    }

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

    const toolsPage = document.querySelector(".tools-page");
    const toolNavLinks = toolsPage ? Array.from(toolsPage.querySelectorAll(".tools-sidebar a[href^='#']")) : [];
    const toolSections = toolsPage ? Array.from(toolsPage.querySelectorAll(".tools-section[id]")) : [];
    if (toolNavLinks.length && toolSections.length) {
        const setActiveTool = (id) => {
            toolNavLinks.forEach((link) => {
                link.classList.toggle("is-active", link.getAttribute("href") === `#${id}`);
            });
        };

        const updateActiveTool = () => {
            const checkpoint = window.scrollY + 150;
            const current = toolSections.reduce((active, section) => {
                return section.offsetTop <= checkpoint ? section : active;
            }, toolSections[0]);
            if (current?.id) setActiveTool(current.id);
        };

        updateActiveTool();
        window.addEventListener("scroll", updateActiveTool, { passive: true });
    }
});

function parseToolSearchIndex(element) {
    try {
        return JSON.parse(element.textContent || "[]").map((entry) => ({
            ...entry,
            searchText: normalizeSearch(`${entry.label || ""} ${entry.category || ""} ${entry.aliases || ""}`)
        }));
    } catch {
        return [];
    }
}

function getToolSearchMatches(index, query) {
    const normalizedQuery = normalizeSearch(query);
    const tokens = normalizedQuery.split(" ").filter(Boolean);
    if (!tokens.length) return [];

    return index
        .map((entry) => {
            let score = 0;
            const label = normalizeSearch(entry.label || "");
            const category = normalizeSearch(entry.category || "");
            const searchText = entry.searchText || "";

            if (label === normalizedQuery) score += 140;
            if (label.includes(normalizedQuery)) score += 90;
            if (searchText.includes(normalizedQuery)) score += 72;
            if (tokens.every((token) => searchText.includes(token))) score += 52;
            if (tokens.some((token) => label.startsWith(token))) score += 26;
            if (tokens.some((token) => category.includes(token))) score += 10;

            tokens.forEach((token) => {
                if (label.includes(token)) score += 14;
                if (searchText.includes(token)) score += 5;
            });

            return { ...entry, score };
        })
        .filter((entry) => entry.score > 0)
        .sort((a, b) => b.score - a.score || a.label.localeCompare(b.label));
}

function normalizeSearch(value) {
    return String(value || "")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, " ")
        .trim();
}

function formatBytes(bytes) {
    if (!bytes) return "0 KB";
    const units = ["B", "KB", "MB", "GB"];
    const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    return `${(bytes / Math.pow(1024, index)).toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}
