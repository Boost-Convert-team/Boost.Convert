(function () {
    function initRevealAnimations() {
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
            return;
        }

        revealElements.forEach((element, index) => {
            element.style.setProperty("--reveal-delay", `${Math.min(index * 78, 320)}ms`);
            element.classList.add("is-visible");
        });
    }

    window.BoostReveal = {
        initRevealAnimations
    };
})();
