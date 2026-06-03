document.addEventListener("DOMContentLoaded", () => {
    document.body.classList.add("is-ready");
    createIcons();

    window.BoostNavigation?.initTopbar();
    window.BoostNavigation?.initMegaMenu();
    window.BoostToolSearch?.initToolSearch();
    window.BoostReveal?.initRevealAnimations();
    window.BoostForms?.initUploadZones();
    window.BoostForms?.initLoadingForms();
    window.BoostForms?.initAuthToggle();
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
