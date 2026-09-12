"use client";

import { useLayoutEffect } from "react";

type RevealStyle = "rise" | "slide-left" | "scale" | "slide-right";

const revealStyles: RevealStyle[] = ["rise", "slide-left", "scale", "slide-right"];

function revealTargets(root: HTMLElement) {
  if (root.classList.contains("public-landing-page")) {
    const landingSections = new Set([
      "public-landing-hero",
      "courses-v2-section",
      "results-v2-section",
      "videos-v2-section",
      "testimonials-v2-section",
      "faq-section",
      "callback-section",
      "branches-section",
      "footer-v2",
    ]);

    return Array.from(root.children).filter(
      (element): element is HTMLElement =>
        element instanceof HTMLElement && Array.from(element.classList).some((className) => landingSections.has(className)),
    );
  }

  const pageHero = root.querySelector<HTMLElement>(":scope > .public-page-hero");
  const pageContent = root.querySelector<HTMLElement>(":scope > .public-page-content");
  const footer = root.querySelector<HTMLElement>(":scope > .footer-v2");

  return [
    pageHero,
    ...(pageContent ? Array.from(pageContent.children).filter((element): element is HTMLElement => element instanceof HTMLElement) : []),
    footer,
  ].filter((element): element is HTMLElement => element instanceof HTMLElement);
}

/**
 * Applies non-blocking reveal motion to the public marketing pages only.
 * The layout itself is untouched; every section remains in normal document flow.
 */
export function PublicPageMotion({ rootSelector }: { rootSelector: string }) {
  useLayoutEffect(() => {
    const root = document.querySelector<HTMLElement>(rootSelector);
    if (!root) return;

    const targets = revealTargets(root);
    if (!targets.length) return;

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    targets.forEach((element, index) => {
      element.dataset.publicReveal = revealStyles[index % revealStyles.length];
      element.dataset.publicRevealState = reducedMotion ? "visible" : "pending";
    });

    if (reducedMotion || !("IntersectionObserver" in window)) {
      targets.forEach((element) => {
        element.dataset.publicRevealState = "visible";
      });
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          const element = entry.target as HTMLElement;
          element.dataset.publicRevealState = "visible";
          observer.unobserve(element);
        });
      },
      { rootMargin: "0px 0px -10%", threshold: 0.08 },
    );

    targets.forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, [rootSelector]);

  return null;
}
