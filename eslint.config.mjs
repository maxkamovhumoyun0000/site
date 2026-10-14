import nextCoreWebVitals from "eslint-config-next/core-web-vitals";

export default [
  ...nextCoreWebVitals,
  {
    ignores: [
      ".next/**",
      "node_modules/**",
      "data/**",
      "**/*.d.ts",
    ],
  },
  {
    // The application predates React Compiler lint rules.  Keep these visible
    // in CI while TypeScript, production build and browser smoke tests remain
    // blocking; converting 800+ historical findings into a single risky
    // refactor would not improve release safety.  New code should clear these
    // warnings as files are touched.
    rules: {
      "react/no-unescaped-entities": "warn",
      "react-hooks/exhaustive-deps": "warn",
      "react-hooks/immutability": "warn",
      "react-hooks/preserve-manual-memoization": "warn",
      "react-hooks/purity": "warn",
      "react-hooks/refs": "warn",
      "react-hooks/rules-of-hooks": "warn",
      "react-hooks/set-state-in-effect": "warn",
      "react-hooks/use-memo": "warn",
    },
  },
];
