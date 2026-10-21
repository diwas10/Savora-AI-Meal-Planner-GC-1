# Savora — Screens and Navigation Contract

## Navigation
Exactly four primary bottom tabs: **Home**, **My Plan**, **Discover**, **Profile**. The **Logout** action is in Profile, not a fifth tab. Suggested Next.js routes: `/dashboard`, `/meal-plans`, `/discover`, `/profile`. Supporting authentication/onboarding routes are outside the tab shell.

## Home (`/dashboard`)
**Goal:** Show today's *planned* meals and the next useful action.
- Header/greeting and current plan context.
- Planned daily nutrition summary (energy, protein, carbohydrates, fat; other nutrients in detail).
- Breakfast, lunch and dinner cards with dishes, portions and planned energy.
- View meal details; navigate to My Plan.
- If no plan exists, show a clear `Generate my 7-day plan` empty state.
- Do not imply meals were consumed or add consumption controls.

## My Plan (`/meal-plans`)
**Goal:** Generate, view and manage a seven-day/21-slot plan.
- Select a saved generated plan; generate another without overwriting previous plans.
- Seven-day selector and three meal cards for the selected day.
- Detail sheet: combination, component portions in household units and grams, nutrients and concise rule-backed explanation.
- `Substitute meal` launches the full substitution workflow; allow natural-language preferences, show eligible alternatives and validate through the full pipeline before saving.
- Keep unchanged slots locked during substitution. If infeasible, explain without silently changing other slots.
- Distinguish generating, feasible, infeasible and failed states.

## Discover (`/discover`)
**Goal:** Offer safe standalone dish recommendations based on cravings.
- Text input such as `Something spicy and Chinese, without noodles` and optional prompt chips.
- Pipeline: Qwen structured intent -> recipe retrieval -> deterministic rule filtering -> Transformer ranking (or documented cold-start fallback).
- Show ranked individual recipes, standard serving, available nutrition and reason for eligibility where supported.
- No Meal Composition Engine, weekly CSP, daily-budget optimization or automatic plan modification.
- Empty/no-safe-match state explains why no recommendation is available and invites refinement.

## Profile (`/profile`)
**Goal:** Display and edit profile, restrictions and calculated nutrition targets.
- Body metrics, age, activity, dietary pattern, allergies, health conditions, cuisine preferences and exploration preference.
- Display versioned nutrition targets computed during onboarding; recalculate only after relevant profile changes.
- Clearly label targets as estimated/planning guidance, not clinical prescriptions.
- Access saved plans as appropriate; include a clearly discoverable **Logout** button.

## Supporting flows
- **Authentication:** login, registration, logout.
- **Onboarding:** short steps for body/activity, dietary/cultural restrictions, allergens/health conditions and cuisine preferences; review calculated targets before plan generation.
- **Meal details:** accessible sheet/page reused from Home and My Plan.
- **Substitution:** request -> Qwen parse -> rule-safe compositions -> Transformer rank -> CSP validate with locked slots -> persist changed slot and substitution record.

## Shared UX states
Every screen or workflow must handle: initial loading, empty state, validation errors, unavailable data, server failure and success. Do not fabricate progress percentages or nutrition values. Preserve user input after recoverable failures. Confirm destructive/logout actions only when useful; avoid needless confirmation steps.
