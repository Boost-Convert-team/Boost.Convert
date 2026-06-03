(function () {
    function normalizeSearch(value) {
        return String(value || "")
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, " ")
            .trim();
    }

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

    function formatBytes(bytes) {
        if (!bytes) return "0 KB";
        const units = ["B", "KB", "MB", "GB"];
        const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
        return `${(bytes / Math.pow(1024, index)).toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
    }

    window.BoostUtils = {
        formatBytes,
        getToolSearchMatches,
        parseToolSearchIndex
    };
})();
