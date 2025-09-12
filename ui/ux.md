# UI/UX Design Principles — EcoLang Playground

This page captures the UI/UX principles guiding the EcoLang app. Each principle includes how it’s applied here and a quick rationale.

## Core principles

- Clarity over cleverness

  - Use plain labels (Editor, Saved Scripts, About). Button text reflects actions (Run, Save, Clear).
  - Error panel shows line, column, and a caret codeframe for quick fixes.

- Progressive disclosure

  - Inputs offer JSON by default with an optional Form mode for approachability.
  - Advanced settings live in API Base input and are not prominent in the main flow.

- Feedback and status

  - “Running...” placeholder and aria-live on output/errors for assistive tech.
  - Warnings are grouped and clearly separated from output; eco card surfaces impact metrics.

- Consistency

  - Same header, tabs, panel layout across tabs; light/dark theme toggle is global.
  - Keyboard shortcuts: Ctrl+Enter to run, Ctrl+S to save.

- Accessibility (A11y)

  - Semantic headings and lists in tutorial renderer; role attributes on tabs and errors.
  - Sufficient color contrast, focusable controls, and screen-reader friendly status updates.

- Minimal necessary friction

  - Login/sign-up is a simple inline form; stays in-context (no modal maze).
  - Saved scripts open in place and hydrate code/title without page navigation.

- Error prevention and recovery

  - Inputs Form validates types softly (defaults + notices) and never blocks editing.
  - Clear hints on syntax errors (e.g., “Write: while \u003ccondition\u003e then”).

- Learnability by example

  - About page tutorial includes runnable code blocks (Try it) and inputs blocks (Use as inputs).
  - Short, consistent examples that progressively introduce features.

## Interaction details

- Editor

  - Large textarea for code, visible title, and prominent action buttons.
  - Output area mirrors a console; warnings and eco metrics are adjacent for context.

- Inputs

  - Tabbed switch (JSON/Form) with persistence in localStorage; switching doesn’t lose data.
  - Form rows map types explicitly (string/number/boolean/null/array/object) with defaults.

- Navigation

  - Three top-level tabs; disabled Editor until authenticated for a clear mental model.
  - State (theme, apiBase, inputsMode, token) persisted to reduce repeated setup.

## Writing guidelines

- Button labels: imperative verbs (Run, Save, Clear, Open).
- Tooltips/alt text: describe outcomes (“Run the program”).
- Messages: short, specific, actionable. Prefer “Use: for name = start to end” over generic errors.

## Future UX enhancements

- Inline per-row validation hints in Inputs Form (e.g., number parse errors) without blocking.
- Optional keyboard shortcut palette and a help overlay.
- Syntax highlighting in tutorial code blocks.
- Toasts for async success/fail (save, load) with non-blocking feedback.
