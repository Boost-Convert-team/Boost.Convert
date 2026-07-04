(function () {
    function initTopbar() {
        const topbar = document.querySelector(".topbar");
        const updateTopbar = () => {
            if (!topbar) return;
            topbar.classList.toggle("is-scrolled", window.scrollY > 12);
        };
        updateTopbar();
        window.addEventListener("scroll", updateTopbar, { passive: true });
    }

    function initMegaMenu() {
        const megaDropdown = document.querySelector(".mega-dropdown");
        if (!megaDropdown) return;

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

    function initProfileMenu() {
        const profileMenu = document.querySelector(".profile-menu");
        if (!profileMenu) return;

        const trigger = profileMenu.querySelector(".profile-trigger");
        const closeProfileMenu = () => profileMenu.removeAttribute("open");

        document.addEventListener("click", (event) => {
            if (!profileMenu.open || profileMenu.contains(event.target)) return;
            closeProfileMenu();
        });

        document.addEventListener("keydown", (event) => {
            if (event.key !== "Escape" || !profileMenu.open) return;
            closeProfileMenu();
            trigger?.focus();
        });
    }

    function initMobileMenu() {
        const topbar = document.querySelector(".topbar");
        const toggle = document.querySelector("[data-mobile-menu-toggle]");
        const panel = document.querySelector("[data-mobile-menu]");
        if (!topbar || !toggle || !panel) return;

        const mobileQuery = window.matchMedia("(max-width: 1024px)");

        const setMobileMenuOpen = (isOpen) => {
            topbar.classList.toggle("is-mobile-menu-open", isOpen);
            panel.hidden = !isOpen;
            toggle.setAttribute("aria-expanded", String(isOpen));
            toggle.setAttribute("aria-label", isOpen ? "Fechar menu" : "Abrir menu");
        };

        const closeMobileMenu = () => setMobileMenuOpen(false);

        closeMobileMenu();

        toggle.addEventListener("click", () => {
            setMobileMenuOpen(!topbar.classList.contains("is-mobile-menu-open"));
        });

        document.addEventListener("click", (event) => {
            if (!topbar.classList.contains("is-mobile-menu-open")) return;
            if (topbar.contains(event.target)) return;
            closeMobileMenu();
        });

        document.addEventListener("keydown", (event) => {
            if (event.key !== "Escape" || !topbar.classList.contains("is-mobile-menu-open")) return;
            closeMobileMenu();
            toggle.focus();
        });

        panel.addEventListener("click", (event) => {
            const link = event.target.closest("a[href]");
            if (link) closeMobileMenu();
        });

        const handleViewportChange = () => {
            if (!mobileQuery.matches) closeMobileMenu();
        };

        if (mobileQuery.addEventListener) {
            mobileQuery.addEventListener("change", handleViewportChange);
        } else {
            mobileQuery.addListener(handleViewportChange);
        }
    }

    function initPageTransitions() {
        resetPageTransitionState();
        window.addEventListener("pageshow", resetPageTransitionState);

        document.querySelectorAll("a[href]").forEach((link) => {
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
    }

    function resetPageTransitionState() {
        document.body.classList.remove("is-leaving");
        document.body.classList.add("is-ready");
    }

    function initToolsSidebar() {
        const toolsPage = document.querySelector(".tools-page");
        const toolNavLinks = toolsPage ? Array.from(toolsPage.querySelectorAll(".tools-sidebar a[href^='#']")) : [];
        const toolSections = toolsPage ? Array.from(toolsPage.querySelectorAll(".tools-section[id]")) : [];
        if (!toolNavLinks.length || !toolSections.length) return;

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

    window.BoostNavigation = {
        initMegaMenu,
        initMobileMenu,
        initPageTransitions,
        initProfileMenu,
        initToolsSidebar,
        initTopbar
    };
})();
