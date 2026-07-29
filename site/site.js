const header = document.querySelector("[data-site-header]");
const menuToggle = document.querySelector("[data-menu-toggle]");
const navigation = document.querySelector("[data-site-nav]");
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

function closeMenu() {
  if (!menuToggle || !navigation) {
    return;
  }

  menuToggle.setAttribute("aria-label", "Open navigation menu");
  menuToggle.setAttribute("aria-expanded", "false");
  navigation.classList.remove("is-open");
}

if (header) {
  const updateHeader = () => {
    header.classList.toggle("is-scrolled", window.scrollY > 20);
  };

  updateHeader();
  window.addEventListener("scroll", updateHeader, { passive: true });
}

if (menuToggle && navigation) {
  menuToggle.addEventListener("click", () => {
    const willOpen = menuToggle.getAttribute("aria-expanded") !== "true";
    menuToggle.setAttribute(
      "aria-label",
      `${willOpen ? "Close" : "Open"} navigation menu`,
    );
    menuToggle.setAttribute("aria-expanded", String(willOpen));
    navigation.classList.toggle("is-open", willOpen);
  });

  navigation.addEventListener("click", (event) => {
    if (event.target instanceof HTMLAnchorElement) {
      closeMenu();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeMenu();
      menuToggle.focus();
    }
  });

  document.addEventListener("click", (event) => {
    if (
      navigation.classList.contains("is-open") &&
      event.target instanceof Node &&
      !header?.contains(event.target)
    ) {
      closeMenu();
    }
  });
}

for (const year of document.querySelectorAll("[data-current-year]")) {
  year.textContent = String(new Date().getFullYear());
}

const revealElements = [...document.querySelectorAll("[data-reveal]")];

if (!reducedMotion.matches && "IntersectionObserver" in window) {
  document.documentElement.classList.add("has-js");

  const revealObserver = new IntersectionObserver(
    (entries, observer) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      }
    },
    {
      rootMargin: "0px 0px -8% 0px",
      threshold: 0.08,
    },
  );

  revealElements.forEach((element, index) => {
    element.style.transitionDelay = `${Math.min(index % 5, 3) * 45}ms`;
    revealObserver.observe(element);
  });
} else {
  revealElements.forEach((element) => element.classList.add("is-visible"));
}

const productDetails = [
  ...document.querySelectorAll(".product-card details"),
];

for (const details of productDetails) {
  details.addEventListener("toggle", () => {
    if (!details.open) {
      return;
    }

    for (const otherDetails of productDetails) {
      if (otherDetails !== details) {
        otherDetails.removeAttribute("open");
      }
    }
  });
}
