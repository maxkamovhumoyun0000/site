"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Custom hook that triggers a CSS class when an element scrolls into view.
 * Returns a ref to attach to the element and a boolean `visible` state.
 */
export function useScrollReveal<T extends HTMLElement = HTMLDivElement>(
  threshold = 0.15,
  rootMargin = "0px 0px -40px 0px"
) {
  const ref = useRef<T>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.unobserve(el);
        }
      },
      { threshold, rootMargin }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, [threshold, rootMargin]);

  return { ref, visible };
}

/**
 * Wrapper component that adds scroll-reveal animation to its children.
 */
export function ScrollReveal({
  children,
  className = "reveal",
  as: Tag = "div",
  threshold = 0.15,
  style,
}: {
  children: React.ReactNode;
  className?: string;
  as?: React.ElementType;
  threshold?: number;
  style?: React.CSSProperties;
}) {
  const { ref, visible } = useScrollReveal(threshold);
  const Component = Tag as any;

  return (
    <Component
      ref={ref}
      className={`${className} ${visible ? "visible" : ""}`}
      style={style}
    >
      {children}
    </Component>
  );
}
