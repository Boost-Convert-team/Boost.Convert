document.addEventListener("DOMContentLoaded", () => {
    document.body.classList.add("is-ready");
    createIcons();
    initHeroHeadlineRotator();

    window.BoostNavigation?.initTopbar();
    window.BoostNavigation?.initMegaMenu();
    window.BoostNavigation?.initProfileMenu();
    window.BoostToolSearch?.initToolSearch();
    window.BoostReveal?.initRevealAnimations();
    window.BoostForms?.initUploadZones();
    window.BoostForms?.initHeroUpload();
    window.BoostForms?.initLoadingForms();
    window.BoostForms?.initAuthToggle();
    initFaqAccordion();
    initConversionStatusPage();
    window.BoostNavigation?.initPageTransitions();
    window.BoostNavigation?.initToolsSidebar();
});

function createIcons() {
    if (!window.lucide) return;
    window.lucide.createIcons({
        attrs: {
            "stroke-width": 1.8
        }
    });
}

function initHeroHeadlineRotator() {
    const root = document.querySelector("[data-hero-headline-rotator]");
    if (!root) return;

    const copy = root.querySelector("[data-hero-headline-copy]");
    const phrases = getHeroHeadlinePhrases(root);
    if (!copy || phrases.length < 2) return;

    let index = 0;
    window.setInterval(() => {
        index = (index + 1) % phrases.length;
        swapHeroHeadlinePhrase(copy, phrases[index]);
    }, 3000);
}

function getHeroHeadlinePhrases(root) {
    return String(root.dataset.heroPhrases || "")
        .split("|")
        .map((phrase) => phrase.trim())
        .filter(Boolean)
        .map(splitHeroHeadlinePhrase);
}

function splitHeroHeadlinePhrase(phrase) {
    const separatorIndex = phrase.indexOf(" ");
    if (separatorIndex < 0) return { prefix: "", word: phrase };

    return {
        prefix: phrase.slice(0, separatorIndex),
        word: phrase.slice(separatorIndex + 1)
    };
}

function swapHeroHeadlinePhrase(copy, phrase) {
    copy.classList.remove("is-active");
    copy.classList.add("is-exiting");

    window.setTimeout(() => {
        renderHeroHeadlinePhrase(copy, phrase);
        copy.classList.remove("is-exiting");
        copy.classList.add("is-entering");
        requestAnimationFrame(() => activateHeroHeadlinePhrase(copy));
    }, 640);
}

function renderHeroHeadlinePhrase(copy, phrase) {
    const prefix = copy.querySelector("[data-hero-headline-prefix]");
    const word = copy.querySelector("[data-hero-headline-word]");
    if (!prefix || !word) return;

    prefix.textContent = phrase.prefix;
    word.textContent = phrase.word;
}

function activateHeroHeadlinePhrase(copy) {
    requestAnimationFrame(() => {
        copy.classList.remove("is-entering");
        copy.classList.add("is-active");
    });
}

function initFaqAccordion() {
    const root = document.querySelector("[data-faq-accordion]");
    if (!root) return;

    const items = Array.from(root.querySelectorAll(".faq-item"));
    const buttons = items
        .map((item) => item.querySelector(".faq-question"))
        .filter(Boolean);

    items.forEach((item) => {
        const button = item.querySelector(".faq-question");
        const answer = getFaqAnswer(item);
        if (!button || !answer) return;

        setFaqItemOpen(item, item.classList.contains("is-open"));

        button.addEventListener("click", () => {
            if (item.classList.contains("is-open")) {
                closeFaqItem(item);
                return;
            }

            items.forEach((otherItem) => {
                if (otherItem !== item) closeFaqItem(otherItem);
            });
            openFaqItem(item);
        });

        button.addEventListener("keydown", (event) => {
            handleFaqKeyboard(event, buttons);
        });
    });
}

function getFaqAnswer(item) {
    const button = item.querySelector(".faq-question");
    if (!button) return null;

    return document.getElementById(button.getAttribute("aria-controls"));
}

function setFaqItemOpen(item, isOpen) {
    const button = item.querySelector(".faq-question");
    const answer = getFaqAnswer(item);
    if (!button || !answer) return;

    item.classList.toggle("is-open", isOpen);
    button.setAttribute("aria-expanded", String(isOpen));
    answer.hidden = false;
    answer.setAttribute("aria-hidden", String(!isOpen));
}

function openFaqItem(item) {
    setFaqItemOpen(item, true);
}

function closeFaqItem(item) {
    setFaqItemOpen(item, false);
}

function handleFaqKeyboard(event, buttons) {
    const currentIndex = buttons.indexOf(event.currentTarget);
    if (currentIndex < 0) return;

    const keyActions = {
        ArrowDown: () => buttons[(currentIndex + 1) % buttons.length].focus(),
        ArrowUp: () => buttons[(currentIndex - 1 + buttons.length) % buttons.length].focus(),
        Home: () => buttons[0].focus(),
        End: () => buttons[buttons.length - 1].focus()
    };

    const action = keyActions[event.key];
    if (!action) return;

    event.preventDefault();
    action();
}

function initConversionStatusPage() {
    const root = document.querySelector("[data-conversion-status-page]");
    if (!root) return;

    showLongConversionMessage(root);
    startConversionStatusPolling(root);
}

function showLongConversionMessage(root) {
    const note = root.querySelector("[data-delayed-conversion-note]");
    if (!note) return;

    window.setTimeout(() => {
        note.hidden = false;
        note.classList.add("is-visible");
    }, 10000);
}

function startConversionStatusPolling(root) {
    const urls = getConversionStatusUrls(root);
    if (urls.length === 0) return;

    window.setInterval(() => {
        refreshCompletedConversionStatus(urls);
    }, 3000);
}

function getConversionStatusUrls(root) {
    try {
        return JSON.parse(root.dataset.statusUrls || "[]");
    } catch (error) {
        return [];
    }
}

async function refreshCompletedConversionStatus(urls) {
    try {
        const statuses = await Promise.all(urls.map(fetchConversionStatus));
        if (statuses.length > 0 && statuses.every(isConversionStatusReady)) {
            window.location.reload();
        }
    } catch (error) {
        return;
    }
}

async function fetchConversionStatus(url) {
    const response = await fetch(url, { headers: { Accept: "application/json" } });
    if (!response.ok) return "";

    const payload = await response.json();
    return String(payload.status || "");
}

function isConversionStatusReady(status) {
    const pendingStatuses = ["queued", "processing"];
    if (!status) return false;

    return !pendingStatuses.includes(status);
}
