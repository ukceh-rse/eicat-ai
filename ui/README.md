# EICAT AI UI

## Reviewing impacts

An analysis lists each of its papers in its own section, including papers not run yet. A paper's section holds its impacts, with buttons to add an impact from that paper and to remove the paper from the analysis. The AI's output is a starting point for expert review:

- **Verify** an AI impact with its checkbox once you have checked it. The paper header shows how many of its active impacts are verified (impacts you added count as verified).
- **Edit** an impact in the table. Category, mechanism, confidence and impacted species are changed in their cells; categories are listed most severe first, and choosing MR or MV asks for reversibility before saving. The row's details (the arrow button) hold alien species and justification. Each change is saved straight away and verifies the impact. An AI impact you changed shows "AI, edited" as its origin, with the AI's values on hover and in the row's details.
- **Evidence** is always text from the paper. Clicking an impact's evidence opens its evidence page, with the paper beside a list of its passages. Select text in the paper and click "Add passage" to add one, remove passages from the list, and save. Where the AI didn't quote word for word, the evidence is the closest passage in the paper, marked with an info icon; a warning icon marks AI sentences not found in the paper at all. Hovering either icon shows the AI's wording.
- **Add an impact** with the add button on a paper's section: select its evidence in the paper, fill in its fields beside it, and save.
- **Remove** an impact, and see its **history**, from the row's menu (⋮). Removed impacts are listed under "Removed" for the paper and can be restored.
- Every action can take an optional **reason**. In the table, type it in the row's details; it is recorded with the next change saved on that impact. The history shows who (AI, system or a reviewer) did what, when, and what changed.

Papers are read on their own page, opened from the Papers list.

### Re-running

Running an analysis again replaces the unverified AI impacts. A dialog shows how many impacts will be kept and how many replaced, and lets you keep or discard verified impacts (discarding asks for a second confirmation). Impacts you added or removed are never changed. If the new run finds an impact whose mechanism is already covered by one you verified, added or removed for that paper, it is listed under "Suppressed" with each run's version, and can be restored from there. Review is paused while an analysis runs.

# React + TypeScript + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react/README.md) uses [Babel](https://babeljs.io/) for Fast Refresh
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react-swc) uses [SWC](https://swc.rs/) for Fast Refresh

## Expanding the ESLint configuration

If you are developing a production application, we recommend updating the configuration to enable type aware lint rules:

- Configure the top-level `parserOptions` property like this:

```js
export default tseslint.config({
  languageOptions: {
    // other options...
    parserOptions: {
      project: ['./tsconfig.node.json', './tsconfig.app.json'],
      tsconfigRootDir: import.meta.dirname,
    },
  },
})
```

- Replace `tseslint.configs.recommended` to `tseslint.configs.recommendedTypeChecked` or `tseslint.configs.strictTypeChecked`
- Optionally add `...tseslint.configs.stylisticTypeChecked`
- Install [eslint-plugin-react](https://github.com/jsx-eslint/eslint-plugin-react) and update the config:

```js
// eslint.config.js
import react from 'eslint-plugin-react'

export default tseslint.config({
  // Set the react version
  settings: { react: { version: '18.3' } },
  plugins: {
    // Add the react plugin
    react,
  },
  rules: {
    // other rules...
    // Enable its recommended rules
    ...react.configs.recommended.rules,
    ...react.configs['jsx-runtime'].rules,
  },
})
```
