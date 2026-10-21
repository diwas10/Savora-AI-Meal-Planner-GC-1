# Savora — Frontend Design System

## Purpose and source of truth
Implement a premium, calm, mobile-first wellness PWA with Apple-inspired translucent navigation and polished native-app interactions. This document defines behavior, layout, component standards and accessibility—not color values. **All colors, surface tokens, gradients and theme values must be defined once in the Tailwind theme/global CSS design tokens.** Components must reference semantic tokens; never hardcode hex/RGB/HSL values in individual components.

## Design principles
1. Prioritize clarity and usability over visual effects. The interface must be understandable without a tutorial.
2. Use a restrained Liquid Glass aesthetic for floating navigation, overlays and transient controls; use opaque, readable surfaces for forms, food cards and dense nutrition information.
3. Make food imagery supportive, not required for comprehension. Every image has a fallback and descriptive alt text.
4. Maintain consistent spacing, radii, elevation, typography and touch behavior through reusable components.
5. Distinguish **planned** nutrition from consumed nutrition; GC1 does not track consumption.

## Layout and responsive behavior
- Design first at a 390px mobile viewport; support narrow phones, tablets and desktop.
- Respect `env(safe-area-inset-top)` and `env(safe-area-inset-bottom)` in standalone PWA mode.
- Mobile: single-column content, comfortable side gutters, sticky/floating bottom navigation and scrollable main content with bottom clearance.
- Tablet/desktop: use a deliberate max-width and responsive composition; do not stretch meal cards into unreadable full-width rows. Navigation may adapt to a sidebar on larger screens if consistent with the same four destinations.
- Avoid horizontal overflow, layout shifts and content hidden behind fixed elements.

## Typography and information hierarchy
- Use one consistent sans-serif type family, defined globally.
- Strong hierarchy: page title, section title, card title, supporting metadata and caption.
- Nutrition numbers require readable units and labels; never convey meaning by color alone.
- Keep primary action labels explicit (`Generate plan`, `View meal`, `Substitute meal`).

## Components
- **App shell:** safe-area-aware header, content region and four-destination bottom navigation.
- **Glass navigation:** translucent backdrop, subtle separation, stable active state, clear labels and icons. Provide a solid-surface fallback where blur is unsupported or reduced transparency is requested.
- **Meal card:** image/fallback, meal slot, combination name, component dishes, portions, planned energy and concise nutrition. Whole card may open detail; secondary actions must not conflict with card tap.
- **Nutrition summary:** planned daily totals and profile targets, with explicit units and labels. Avoid progress metaphors that imply actual consumption.
- **Day selector:** seven-day horizontally scrollable control with selected state, accessible day names and keyboard support.
- **Craving input:** prominent free-text entry, optional suggestion chips, submit/loading state and schema-backed result display.
- **Bottom sheet/dialog:** meal details and substitution flow; focus management, Escape handling, scroll containment and accessible close control.
- **Forms:** visible labels, inline validation, accessible error summaries and appropriate input modes.
- **Buttons:** primary, secondary, subtle and destructive variants; consistent disabled/loading behavior.

## Motion and glass rules
- Motion should clarify state transitions, not delay tasks. Prefer short, subtle transitions.
- Honor `prefers-reduced-motion`; do not require animations to understand state.
- Avoid stacking backdrop blurs, especially over scrolling food lists.
- Use glass only for navigation, overlays or floating controls. Do not place safety warnings or dense nutrient tables on highly transparent surfaces.

## Accessibility and reliability
- Aim for WCAG AA contrast, visible focus indicators and touch targets around 44x44 CSS pixels or larger.
- Use semantic landmarks, real buttons/links, accessible names, keyboard-operable tabs and dialogs.
- Handle loading, empty, error, offline and unknown-data states explicitly.
- Show allergy/dietary exclusions clearly. Never display unverified nutritional data as verified.
- PWA: installable manifest, app icons, standalone viewport and appropriate service-worker behavior; generation and AI inference require connectivity.

## Implementation rules
- Next.js App Router owns routing; reusable screen components live in feature modules.
- Use Tailwind semantic utilities backed by central theme tokens. No inline hardcoded color values.
- Prefer shadcn/ui or accessible Radix primitives where appropriate; adapt them to the shared system rather than styling each screen independently.
- Use Lucide icons consistently. Use TanStack Query for server state, React Hook Form + Zod for forms.
- Check mobile Safari, Android Chrome and desktop responsive behavior. Verify safe areas and bottom-sheet scrolling.
