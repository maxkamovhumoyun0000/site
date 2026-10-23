(() => {
  "use strict";

  const attribute = "data-csp-style";
  const allowedProperties = new Set([
    "--sway",
    "accentColor", "alignItems", "alignSelf", "animation", "animationDelay",
    "animationDuration", "aspectRatio", "backdropFilter", "background", "border",
    "borderBottom", "borderCollapse", "borderColor", "borderLeft", "borderRadius",
    "borderRight", "borderTop", "borderTopColor", "boxShadow", "boxSizing", "color",
    "cursor", "display", "filter", "flex", "flexDirection", "flexShrink", "flexWrap",
    "fontFamily", "fontSize", "fontWeight", "gap", "gridColumn", "gridTemplateColumns",
    "height", "inset", "justifyContent", "left", "letterSpacing", "lineHeight", "margin",
    "marginBottom", "marginLeft", "marginRight", "marginTop", "maxHeight", "maxWidth",
    "minHeight", "minWidth", "objectFit", "opacity", "outline", "overflow", "overflowX",
    "overflowY", "overscrollBehavior", "padding", "paddingBottom", "paddingLeft",
    "paddingTop", "placeItems", "pointerEvents", "position", "resize", "right", "textAlign",
    "textDecoration", "textOverflow", "textTransform", "top", "touchAction", "transform",
    "transformOrigin", "transition", "userSelect", "verticalAlign", "WebkitBoxOrient",
    "WebkitLineClamp", "WebkitOverflowScrolling", "whiteSpace", "width", "zIndex",
  ]);
  const unitlessProperties = new Set([
    "animationIterationCount", "aspectRatio", "borderImageOutset", "borderImageSlice",
    "borderImageWidth", "boxFlex", "boxFlexGroup", "boxOrdinalGroup", "columnCount",
    "columns", "flex", "flexGrow", "flexPositive", "flexShrink", "flexNegative",
    "flexOrder", "gridArea", "gridRow", "gridRowEnd", "gridRowSpan", "gridRowStart",
    "gridColumn", "gridColumnEnd", "gridColumnSpan", "gridColumnStart", "fontWeight",
    "lineClamp", "lineHeight", "opacity", "order", "orphans", "tabSize", "widows",
    "zIndex", "zoom", "fillOpacity", "floodOpacity", "stopOpacity", "strokeDasharray",
    "strokeDashoffset", "strokeMiterlimit", "strokeOpacity", "strokeWidth",
  ]);
  const unsafeValue = /(?:url\s*\(|expression\s*\(|@import|javascript\s*:|vbscript\s*:|behavior\s*:|[\u0000-\u001f<>;{}])/i;
  const applied = new WeakMap();

  function isIgnored(element) {
    return element.closest('[data-csp-style-ignore]') !== null;
  }

  function clearAppliedStyle(element) {
    const previous = applied.get(element) || new Set();
    for (const property of previous) element.style.removeProperty(property);
    applied.set(element, new Set());
  }

  function cssName(property) {
    return property
      .replace(/^Webkit([A-Z])/, (_, letter) => `-webkit-${letter.toLowerCase()}`)
      .replace(/^ms([A-Z])/, (_, letter) => `-ms-${letter.toLowerCase()}`)
      .replace(/[A-Z]/g, (letter) => `-${letter.toLowerCase()}`)
      .toLowerCase();
  }

  function safeValue(property, value) {
    if (value == null || typeof value === "boolean") return null;
    if (typeof value === "number") {
      if (!Number.isFinite(value)) return null;
      return value !== 0 && !unitlessProperties.has(property) ? `${value}px` : String(value);
    }
    if (typeof value !== "string") return null;
    const trimmed = value.trim();
    if (!trimmed || trimmed.length > 512 || unsafeValue.test(trimmed)) return null;
    return trimmed;
  }

  function applyStyle(element) {
    const previous = applied.get(element) || new Set();
    if (isIgnored(element)) {
      clearAppliedStyle(element);
      return;
    }
    const raw = element.getAttribute(attribute);
    let input = null;
    if (raw && raw.length <= 8192) {
      try {
        input = JSON.parse(raw);
      } catch {
        input = null;
      }
    }
    const next = new Set();
    if (input && typeof input === "object" && !Array.isArray(input)) {
      for (const [property, rawValue] of Object.entries(input)) {
        if (!allowedProperties.has(property)) continue;
        const value = safeValue(property, rawValue);
        const name = cssName(property);
        if (value == null) {
          element.style.removeProperty(name);
          continue;
        }
        element.style.setProperty(name, value);
        next.add(name);
      }
    }
    for (const property of previous) {
      if (!next.has(property)) element.style.removeProperty(property);
    }
    applied.set(element, next);
  }

  function scan(node) {
    if (!node || node.nodeType !== 1) return;
    const element = node;
    if (isIgnored(element)) {
      clearAppliedStyle(element);
      for (const child of element.querySelectorAll(`[${attribute}]`)) clearAppliedStyle(child);
      return;
    }
    if (element.hasAttribute(attribute)) applyStyle(element);
    for (const child of element.querySelectorAll(`[${attribute}]`)) {
      if (!isIgnored(child)) applyStyle(child);
    }
  }

  const observer = new MutationObserver((records) => {
    for (const record of records) {
      if (record.type === "attributes") {
        if (record.attributeName === "data-csp-style-ignore") scan(record.target);
        else applyStyle(record.target);
      }
      for (const node of record.addedNodes || []) scan(node);
    }
  });
  observer.observe(document.documentElement, {
    subtree: true,
    childList: true,
    attributes: true,
    // React hydration or a UI library may rewrite style declarations; reapply
    // the trusted allowlisted payload after those DOM attribute mutations.
    attributeFilter: [attribute, "data-csp-style-ignore", "style"],
  });
  scan(document.documentElement);
})();
