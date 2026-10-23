# Demo evidence (22 October 2026)

Captured with Playwright driving Microsoft Edge (390×844 phone viewport unless noted)
against the real stack: FastAPI on PostgreSQL 16, the real catalogue pipelines, the
Transformer (`sasrec-content-v2+pop8`), Member 2's weekly search v2 and local Ollama
`qwen3:0.6b`. Nothing is mocked. The plan took 52 s and the swap 50 s.

| Screen | File |
|---|---|
| Landing | `01-landing.png` |
| Onboarding, step 1 | `03-onboarding-about.png` |
| Estimated targets before planning | `06-targets.png` |
| Home: planned meals and planned-vs-target ranges | `10-home.png` |
| Meal detail sheet | `12-meal-detail.png` |
| My Plan: seven-day selector | `13-my-plan.png` |
| Swap: words read as chips, ranked eligible meals | `16-swap-options.png` |
| Swap result: before/after, new plan version | `18-swap-result.png` |
| Discover chat: ranked dishes for a craving | `20-discover-reply.png` |
| Discover: swap hand-off to My Plan | `21-discover-swap.png` |
| Profile and versioned targets | `22-profile.png` |
| Dark mode | `r-dark-plan.png` |
| Offline: saved plan still readable | `r-offline-plan.png` |
| Desktop (1280 wide) with sidebar | `23-desktop-plan.png` |

## Swap with Member 2's compact B1 proof (23 October 2026)

Same stack, `SWAP_PROOF_MODE=required` (ADR 0007): mixed Indian vegetarian with a milk
allergy, D1 breakfast swapped. The weekly CSP accepted the swap in 48 s. The compact B1 proof
then returned VALID, was independently verified, and was stored with certificate
`ea94019c…4540e34` and the changed day's exact native totals (proof 235 s, 282 s in all).

| Screen | File |
|---|---|
| Swap: CSP passed, independent proof running | `24-swap-verifying.png` |
| Swap result with "Swap independently verified" | `25-swap-verified.png` |

| Targets card with nutrient ranges, per-meal energy and the calculation steps (23 October) | `26-targets-breakdown.png` |

## Forgot password (23 October 2026)

Real stack; the mail goes to the backend log because no SMTP server is configured. Flow: link on sign-in, request, link from the log, new password, old password refused, new one signs in, the link refused a second time.

| Screen | File |
|---|---|
| Request a reset link | `27-forgot-password.png` |
| Link sent (same text for any email) | `28-reset-link-sent.png` |
| Choose a new password | `29-reset-password.png` |
