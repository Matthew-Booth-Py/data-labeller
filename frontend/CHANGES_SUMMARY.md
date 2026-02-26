# Frontend Change Summary

This summary captures the UI/UX revamp implemented across the frontend.

## 1. Design System Foundation
- Added semantic design tokens and Beazley semantic mapping in `client/src/theme/design-tokens.ts`.
- Expanded global CSS token contract in `client/src/index.css`:
  - surfaces, text roles, interaction roles, status colors, border roles
  - added missing variables (`--button-outline`, `--badge-outline`)
  - added global interaction utilities (`hover-elevate`, `active-elevate-2`)

## 2. Core UI Primitive Refresh
- Updated component primitives to align to the new token system:
  - `client/src/components/ui/button.tsx`
  - `client/src/components/ui/badge.tsx`
  - `client/src/components/ui/card.tsx`
  - `client/src/components/ui/input.tsx`
  - `client/src/components/ui/tabs.tsx`
- Added explicit productivity variants for buttons/badges while keeping compatibility aliases.

## 3. App Chrome and Navigation
- Rebuilt shell layout in `client/src/components/layout/Shell.tsx`:
  - top utility bar + branded header
  - persistent left project rail
  - responsive mobile drawer rail
  - new `ShellProps` API with section/page/action context
- Locked global app theme to brand-light in `client/src/App.tsx`.

## 4. Page-Level Redesign
- Updated top-level pages to the new shell API and hierarchy:
  - `client/src/pages/Dashboard.tsx`
  - `client/src/pages/ProjectsList.tsx`
  - `client/src/pages/CreateProject.tsx`
  - `client/src/pages/FieldsLibrary.tsx`
  - `client/src/pages/Settings.tsx`
  - `client/src/pages/Extraction.tsx`
- Refactored workspace page with typed tab IDs in:
  - `client/src/pages/ProjectWorkspace.tsx`

## 5. Workspace Surface Improvements
- Updated module-level layouts and controls for readability/responsiveness:
  - `client/src/components/workspace/DocumentPool.tsx`
  - `client/src/components/workspace/SchemaViewer.tsx`
  - `client/src/components/workspace/ExtractionRunner.tsx`
  - `client/src/components/workspace/LabelsView.tsx`
  - `client/src/components/workspace/EvaluateView.tsx`
  - `client/src/components/workspace/DeploymentView.tsx`
  - `client/src/components/workspace/APIManagement.tsx`
- Kept `DataLabellerV2` dark-mode specialist styling, while aligning typography/spacing language through shared CSS.

## 6. Documentation Added
- Added implementation handoff spec:
  - `frontend/UI_REVAMP_SPEC.md`

## 7. Validation Completed
- `npm --prefix frontend run check` passed.
- `npm --prefix frontend run build` passed.
- Build emits chunk-size warning only (non-blocking).
