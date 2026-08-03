"use client";

import { type ReactNode, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

export function ModalPortal({
  open,
  children,
}: {
  open: boolean;
  children: ReactNode;
}) {
  const [mounted, setMounted] = useState(false);
  const previousBodyOverflow = useRef("");
  const previousBodyPaddingRight = useRef("");
  const previousHtmlOverscroll = useRef("");

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!open || !mounted) return;
    previousBodyOverflow.current = document.body.style.overflow;
    previousBodyPaddingRight.current = document.body.style.paddingRight;
    previousHtmlOverscroll.current = document.documentElement.style.overscrollBehavior;

    const scrollbarWidth = Math.max(0, window.innerWidth - document.documentElement.clientWidth);
    document.body.style.overflow = "hidden";
    if (scrollbarWidth > 0) {
      document.body.style.paddingRight = `${scrollbarWidth}px`;
    }
    document.documentElement.style.overscrollBehavior = "contain";
    document.documentElement.classList.add("modal-portal-open");

    return () => {
      document.body.style.overflow = previousBodyOverflow.current;
      document.body.style.paddingRight = previousBodyPaddingRight.current;
      document.documentElement.style.overscrollBehavior = previousHtmlOverscroll.current;
      document.documentElement.classList.remove("modal-portal-open");
    };
  }, [mounted, open]);

  if (!mounted || !open) return null;
  return createPortal(children, document.body);
}
