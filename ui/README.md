# EICAT AI UI

## Reviewing impacts

After an analysis runs, its impacts are listed per paper under **Results**. The AI's output is a starting point for expert review:

- **Verify** an AI impact with its checkbox once you have checked it. The paper header shows how many of its active impacts are verified (impacts you added count as verified).
- **Edit** an impact with the pencil button. Every field can be changed; reversibility is asked for only when the category is MR or MV. Saving an edit also verifies the impact. Fields that differ from the AI's original are marked, and hovering the "Changed from AI" chip shows the AI's values.
- **Evidence** is always text from the paper. "Show in paper" opens the paper with the evidence highlighted. To change it, choose "Edit evidence" in the edit dialog, select passages in the paper, click "Add passage" for each, then "Use as evidence". A warning marks AI evidence that could not be found in the paper.
- **Add an impact** with the add button on a paper in the **Papers** list: select its evidence in the paper, choose "Add impact", and fill in the form.
- **Remove** an impact with the bin button. Removed impacts are listed under "Removed" for the paper and can be restored.
- Every action can take an optional **reason**, and the history button shows an impact's full history: who (AI, system or a reviewer) did what, when, and what changed.

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
