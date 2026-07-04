(function () {
    function initToolSearch() {
        const searchDataElement = document.getElementById("tool-search-data");
        const utils = window.BoostUtils;

        if (!searchDataElement || !utils) return;

        const toolSearchIndex = utils.parseToolSearchIndex(searchDataElement);
        document.querySelectorAll("[data-tool-search]").forEach((searchForm) => {
            initSingleToolSearch(searchForm, toolSearchIndex, utils);
        });
    }

    function initSingleToolSearch(searchForm, toolSearchIndex, utils) {
        const searchInput = searchForm.querySelector("[data-tool-search-input]");
        const searchResults = searchForm.querySelector("[data-tool-search-results]");
        if (!searchInput || !searchResults) return;

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

            currentSearchResults = utils.getToolSearchMatches(toolSearchIndex, query).slice(0, 7);

            if (!currentSearchResults.length) {
                const empty = document.createElement("div");
                empty.className = "tool-search-empty";
                empty.textContent = "Nenhuma ferramenta encontrada";
                searchResults.appendChild(empty);
                searchForm.classList.add("is-open");
                return;
            }

            currentSearchResults.forEach((entry, index) => {
                searchResults.appendChild(createSearchResult(entry, index, activeSearchIndex, setActiveSearchResult));
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

    function createSearchResult(entry, index, activeSearchIndex, setActiveSearchResult) {
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
        return link;
    }

    window.BoostToolSearch = {
        initToolSearch
    };
})();
