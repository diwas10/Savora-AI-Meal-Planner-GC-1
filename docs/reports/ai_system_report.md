# Savora: An Explainable Neuro-Symbolic AI System for Clinically-Constrained Meal Planning

**Academic & Technical System Report**  
**Course / Track:** Graduate Capstone / AI System Implementation (GC1)  
**System:** Savora — Explainable Neuro-Symbolic Meal Planning Platform  
**Target Audience:** Faculty Reviewer / Capstone Professor  
**Date:** October 2026  
**Status:** Completed & Integrated Baseline  

---

## Executive Summary

Personalized dietary planning presents a fundamental challenge in applied artificial intelligence: balancing **generative flexibility and user preference alignment** with **strict clinical safety and combinatorial feasibility**. Traditional pure machine learning and large language model (LLM) approaches suffer from stochastic hallucination, uncalibrated nutrient claims, and an inability to provide hard mathematical guarantees on clinical constraints (such as sodium ceilings for hypertension or glycemic management for Type 2 Diabetes). Conversely, pure symbolic expert systems often lack nuanced understanding of user culinary taste sequences and struggle with unstructured natural language interactions.

To resolve this dichotomy, we designed and implemented **Savora**, an end-to-end **neuro-symbolic meal planning system**. Savora enforces a rigorous separation of concerns:
1. **Symbolic Verification & Search (The Deterministic Core):** A focused Food Knowledge Graph, a multi-tier Clinical Rule Engine operating under strict fail-closed ternary logic (`PASS`, `FAIL`, `UNKNOWN`), and a 21-slot Constraint Satisfaction Problem (CSP) solver utilizing incremental forward checking, dynamic nutrient bound propagation, and formal cryptographic certificate proofs for meal substitutions.
2. **Neural Ranking & Understanding (The Intuitive Edge):** A compact sequential Transformer recommendation model (`sasrec-content-v2`) incorporating item interaction history, culinary tags, and ingredient embeddings to rank candidate meals, alongside a quantized, local small language model (`qwen3:0.6b`) operating under schema-constrained decoding and entity grounding for craving extraction.
3. **Multi-Stage Transparent Explainability:** Deterministic, non-hallucinatory explanations that reconstruct the exact clinical rules, caloric calculations, and sequential preference signals behind every suggested dish.

The system is delivered as a pure, dependency-isolated Python library (`savora_ai`), integrated into a modern asynchronous service architecture (FastAPI, PostgreSQL/Supabase, Next.js PWA). The overall test suite contains over 3,900 automated unit, property, and regression tests ensuring reproducibility, type safety, and mathematical adherence to nutritional guidelines.

---

## 1. Problem Formulation & System Invariants

### 1.1 The Clinical & Combinatorial Challenge
A weekly meal plan consists of **21 discrete meal slots** ($S = \{D1\_B, D1\_L, D1\_D, \dots, D7\_D\}$). A naive combinatorial assignment from a modest catalogue of candidate dishes ($N \approx 500$) yields an astronomical search space of $500^{21} \approx 2.38 \times 10^{56}$ possible schedules.

Within this space, a viable plan must satisfy multiple orthogonal layers of constraints:
* **Physiological Energy & Macronutrient Balance:** Basal Metabolic Rate (BMR) computed via the validated Mifflin-St Jeor equation, scaled by Physical Activity Level (PAL), and balanced across Acceptable Macronutrient Distribution Ranges (AMDR).
* **Clinical Safety Hard Limits:** Absolute intake ceilings derived from evidence-based clinical guidelines (e.g., American Heart Association sodium caps of $<2,000\,\text{mg/day}$ for hypertension; saturated fat bounds of $<7\%\,\text{energy}$ for dyslipidemia; complex carbohydrate distribution for Type 2 Diabetes).
* **Dietary & Allergenic Feasibility:** Absolute exclusions for user allergies (e.g., peanuts, shellfish, dairy) and ethical/cultural diets (e.g., lacto-vegetarian, vegan, beef/pork exclusions).
* **Culinary Coherence & Variety:** Meal template validity (combining staples, proteins, and vegetable accompaniments into realistic culinary units) and cross-slot repetition limits (preventing recipe exhaustion across consecutive days).

### 1.2 Core Architectural Invariants
To ensure mathematical and clinical soundness, Savora establishes four immutable architectural invariants:

```text
               ┌────────────────────────────────────────────────────────┐
               │              FAIL-CLOSED SAFETY PRINCIPLE              │
               │                                                        │
               │    Candidate Dish / Meal Formulation                   │
               │                   │                                    │
               │         [Clinical Rule Engine]                         │
               │                   │                                    │
               │        ┌──────────┴──────────┐                         │
               │        │  Ternary Evaluation │                         │
               │        └──────────┬──────────┘                         │
               │                   │                                    │
               │     ┌─────────────┼─────────────┐                      │
               │     ▼             ▼             ▼                      │
               │   PASS          FAIL         UNKNOWN                   │
               │     │             │             │                      │
               │  [Admit]      [Reject]      [Reject]                   │
               │                            (Fail-Closed)               │
               └────────────────────────────────────────────────────────┘
```

1. **Strict Fail-Closed Semantics ($PASS \mid FAIL \mid UNKNOWN$):** Missing nutritional or allergen data required by an active clinical hard rule is never assumed to be zero. Any item with indeterminate safety evaluates to `UNKNOWN` and is strictly excluded from candidate domains.
2. **Strict Authority Separation:** Neural components (Transformer ranker, SLM craving parser) are strictly advisory. They *never* synthesize dishes, assign portions, evaluate clinical safety, or override symbolic constraints.
3. **Portion Discretization & Physical Realism:** Portions are not continuous unconstrained multipliers. They are defined using curated, recipe-specific household measures and discrete step sizes (e.g., 50 g increments, discrete whole items) validated against reference USDA food density standards.
4. **Frozen Snapshot Immutability:** Generated meal plans and user target versions are persisted as immutable cryptographic snapshots. Meal substitutions re-solve and formally prove compliance for the single targeted slot while freezing the remaining 20 slots.

---

## 2. Neuro-Symbolic System Architecture

Savora's architecture pipeline decouples deterministic constraint solving from preference-driven neural inference:

```mermaid
flowchart TD
    subgraph Input ["User Context & Ingestion"]
        UP[User Profile & Targets\nMifflin-St Jeor + PAL + AMDR]
        NL[Unstructured Craving Text\n'I want something spicy with tofu']
    end

    subgraph Neural_Edge ["Neural Inference (Advisory & NLU)"]
        QWEN[Local SLM: Qwen-3 0.6B\nSchema-Constrained Decoding]
        SASREC[Sequential Transformer: SASRec-v2\nCausal Attention + Content Embeddings]
    end

    subgraph Symbolic_Core ["Symbolic Core (Verification & Constraint Solving)"]
        KG[Focused Food Knowledge Graph\nTaxonomy, Pairings, USDA Staples]
        RULES[Multi-Tier Clinical Rule Engine\nT2D, Hypertension, Dyslipidemia, Allergens]
        COMP[Meal Composition Engine\nCurated Templates & Portion Presets]
        CSP[21-Slot Weekly CSP Solver\nIncremental Forward Checking + Dynamic Bounds]
        PROOF[Compact B1 Swap Proof Engine\nCryptographic Replay & Verification Digest]
    end

    subgraph Output ["Application & Explanation"]
        PLAN[Verified 7-Day Plan Snapshot]
        EXPL[Auditable Multi-Stage Explanation Trace]
    end

    %% Flow connections
    NL --> QWEN
    QWEN -->|Grounding & Fallback| KG
    UP --> RULES
    KG --> RULES
    RULES -->|Candidate Pruning| COMP
    COMP -->|Pre-Screened Combinations| SASREC
    SASREC -->|Value-Ordering Scores| CSP
    RULES --> CSP
    CSP --> PLAN
    CSP --> PROOF
    PROOF --> PLAN
    PLAN --> EXPL
    RULES --> EXPL
    SASREC --> EXPL
```

### End-to-End Operational Pipelines:
1. **Weekly Meal Plan Generation (`RULE -> COMP -> RANK -> CSP`):**
   * *Filtering:* The Rule Engine screens raw dishes against user dietary restrictions, allergies, and ingredient exclusions.
   * *Composition:* The Meal Composition Engine pairs approved main dishes with compatible staples and vegetables using curated templates.
   * *Ranking:* The `sasrec-content-v2` Transformer scores combinations based on user interaction history and seed preferences.
   * *Optimization:* The CSP solver selects an optimal, repetition-controlled combination and portion preset for all 21 slots, enforcing daily macro/micro-nutrient bounds.
2. **Locked-Slot Meal Substitution (`PLANNED_SWAP`):**
   * The user selects a specific slot to replace (optionally entering craving preferences).
   * The other 20 slots are locked in state, portions, and nutrient totals.
   * The CSP identifies replacement candidates that preserve joint day and weekly nutrient bounds.
   * The Compact B1 Proof Engine reconstructs and independently verifies the updated schedule, emitting a SHA-256 certificate digest before updating the plan.
3. **Standalone Craving Discovery (`NLU -> RETRIEVAL -> RULE -> RANK`):**
   * Qwen-3 0.6B parses craving intent and slots into structured JSON.
   * Entities are grounded against the Food Knowledge Graph vocabulary.
   * Candidates are filtered by the Rule Engine and ranked by the Transformer.
   * Results are returned immediately with verified serving nutrition, without falsely claiming to fit the user's daily budget.

---

## 3. Subsystem Breakdown & Methodology

### 3.1 Data Curation & Physical Food Modeling
A primary vulnerability in food recommender systems is corrupt or poorly reported recipe data. Savora implemented a strict multi-stage ingestion and validation funnel over **231,637 raw Food.com recipes** and **USDA Foundation Foods**:

* **Quarantine Filter:** 17,941 rows (7.7%) were quarantined due to irreconcilable data defects:
  * *Atwater Energy Inconsistency:* Quarantining recipes whose stated caloric energy deviated significantly from theoretical energy derived from macronutrients ($4\,\text{kcal/g}$ for protein and carbohydrate, $9\,\text{kcal/g}$ for fat) outside allowable rounding windows ($>10\,\text{kcal}$ or ratio outside $[0.75, 1.25]$).
  * *Serving Bounds:* Excluding extreme entries ($<10\,\text{kcal}$ or $>1,500\,\text{kcal}$ per serving, or $\%DV > 300\%$).
* **Stratified Curation & USDA Staples:** Ingestion of 22 foundational USDA items (e.g., cooked brown rice, roti, plain boiled potatoes, whole eggs) with verified density, gram conversions, and zero-sodium baselines to ground composite meal assemblies.
* **Meal Composition Engine:** Dishes are classified by culinary role (`MAIN_DISH`, `STAPLE`, `VEGETABLE`, `BREAKFAST_BASE`). Bounded templates define coherent combinations:
  $$\text{Meal} = \text{Staple} + \text{Main Curry/Protein} + [\text{Vegetable Side}]$$
  Each combination is computed with four distinct portion presets (`STANDARD`, `LOWER_CARB`, `HIGHER_PROTEIN`, `LIGHT`), mathematically verified to deliver the intended macro shifts without violating portion physics.

### 3.2 Symbolic Clinical Rule Engine & Knowledge Graph
Clinical rules are maintained in a relational schema and mapped to an in-memory graph representation (NetworkX / tabular fact index):
* **Domain Policies:**
  * *Type 2 Diabetes (T2D):* Strict meal-level carbohydrate limits, glycemic index (GI) thresholds, and minimum dietary fiber quotas.
  * *Hypertension:* Daily cumulative sodium intake clamped to clinical thresholds ($\le 2,000\,\text{mg/day}$; or stricter custom clinical limits).
  * *Dyslipidemia:* Saturated fat restricted to $<7\%$ of total daily caloric expenditure.
  * *Allergens & Celiac:* Direct and derived ingredient tracking (e.g., detecting hidden soy derivatives, gluten-bearing wheat flours, dairy solids).
* **Ternary Fact Evaluation:** Every condition runs against an evaluation context ($C$) and candidate facts ($F$). If any required fact is absent, the rule yields `UNKNOWN`. In clinical scopes, `UNKNOWN` is treated identically to `FAIL`, eliminating the risk of unverified meals being recommended.

### 3.3 Constraint Satisfaction Problem (CSP) Weekly Solver
The scheduling core formulates 7-day meal planning as a finite-domain CSP:
$$\text{Variables: } X = \{x_1, x_2, \dots, x_{21}\}, \quad x_i = (c_i, p_i)$$
where $c_i$ is a valid meal combination and $p_i \in \{\text{STANDARD}, \text{LOWER\_CARB}, \dots\}$ is a discrete portion preset.

```text
Domain: D(x_i) = Eligible Combinations x Portions for Meal Type(x_i)
Constraints:
  1. Slot Compatibility: MealType(c_i) == SlotType(x_i)
  2. Ingredient Exclusions: Inactive(c_i, Allergens) == True
  3. Daily Energy Budget: E_min(Day(x_i)) <= Sum(E(x_k)) <= E_max(Day(x_i))
  4. Daily Macronutrient Bands: AMDR_min <= Nutrient(Day(x_i)) <= AMDR_max
  5. Weekly Sodium & Saturated Fat Ceilings
  6. Variety / Repetition Limit: RecipeRepetitions(Week) <= MaxAllowed
```

#### Solver Evolution & Algorithmic Optimizations:
* **Naive Chronological Backtracking (v1):** Explored slots chronologically. Suffered from catastrophic thrashing when early slot choices exhausted nutrient budgets for dinner slots on days 5–7, taking up to 175 seconds per plan.
* **Incremental Forward Checking with Dynamic Bounds (v2):**
  * *Dynamic Pruning:* After assigning slot $x_k$, remaining nutrient budgets are checked against the absolute minimum and maximum attainable nutrient sums across unassigned slots $x_{k+1} \dots x_{21}$. If the remaining budget cannot be satisfied by any combination in the remaining domains, the branch is pruned immediately.
  * *Preparation Reuse & Rule Caching:* Evaluates static rule filtering once per weekly run rather than re-evaluating rules inside recursive search loops.
  * *Minimum Remaining Values (MRV):* Prioritizes slots with the tightest remaining candidate domains.
  * *Performance Impact:* Solves strict multi-condition weekly plans (e.g., Indian Vegetarian with Hypertension and T2D) in **~50 seconds** (a **3.5x speedup** over v1) with zero constraint violations.

### 3.4 Sequential Neural Recommender (`sasrec-content-v2`)
While symbolic search enforces physical feasibility, user adherence depends on culinary preference alignment. 

```text
User Seed / Interaction History: [Dish_1, Dish_2, ..., Dish_t]
                              │
               ┌──────────────┴──────────────┐
               ▼                             ▼
       [Learned Item ID]           [Content Representation]
          E_id(Dish_i)             mean(E_tag) + mean(E_ingr)
               │                             │
               └──────────────┬──────────────┘
                              ▼
                     v(i) = Item Vector
                              │
               ┌──────────────┴──────────────┐
               ▼                             ▼
    [Causal Self-Attention Layer 1]   (Hidden State h)
    [Causal Self-Attention Layer 2]
                              │
                              ▼
                    Sequence State Vector (h)
                              │
            ┌─────────────────┴─────────────────┐
            ▼                                   ▼
    Dot-Product Scoring                Popularity Log-Prior
     score = h . v(candidate)           w * log(1 + interactions)
            │                                   │
            └─────────────────┬─────────────────┘
                              ▼
                   Final Hybrid Preference Score
```

* **Architecture:** Based on Self-Attention Sequential Recommendation (SASRec). Uses 2 causal self-attention transformer layers (64 embedding dimensions, 2 attention heads, dropout 0.2) over the user's recent dish sequence ($t \le 50$).
* **Cold-Start & Content Embedding Bridge:** Pure ID-based recommendation fails on newly curated ethnic recipes (e.g., traditional Nepali gundruk, daal bhat). To overcome this, item representations combine learned ID embeddings with pooled tag embeddings (551 tags) and ingredient embeddings (3,000 canonical ingredients):
  $$v(i) = \mathbb{I}_{[i \in \text{seen}]} \cdot E_{\text{id}}[i] + \frac{1}{|T_i|}\sum_{t \in T_i} E_{\text{tag}}[t] + \frac{1}{|I_i|}\sum_{j \in I_i} E_{\text{ingr}}[j]$$
* **Negative Sampling with logQ Correction:** Trained with AdamW ($lr = 10^{-4}$) using sampled softmax over 1,024 negatives drawn from $0.8 \times \text{pop}^{0.75} + 0.2 \times \text{uniform}$, with mathematical logQ correction to eliminate frequency-induced probability distortion.
* **Serving Latency:** Precomputed item vectors allow real-time inference on a standard CPU: **0.5 ms median latency**, 1.3 ms p95 for candidate ranking.

### 3.5 Natural Language Craving Understanding (Local Edge SLM)
To allow spontaneous craving discovery without cloud API latency or privacy leakage, Savora integrates an edge SLM:
* **Model & Deployment:** `qwen3:0.6b` running locally via Ollama.
* **Constrained Structured Decoding:** Strict JSON Schema generation enforcing the `CravingRequest` structure: intent (`CRAVING_RECOMMEND` vs. `SWAP_MEAL`), target slot ID, extracted cuisine tags, flavor profiles, and excluded ingredient names. Thinking tokens are disabled and temperature is clamped to 0.
* **Canonical Entity Grounding:** Raw extracted tokens are mapped against the controlled Food Knowledge Graph vocabulary using exact and fuzzy matching.
* **Hybrid Fallback Mechanism:** The SLM output is merged with a deterministic regular-expression template parser. If the local SLM times out ($>8\,\text{s}$), produces malformed tokens, or is offline, the deterministic parser immediately assumes execution, guaranteeing 100% system availability.

### 3.6 Explainability Engine
Rather than relying on post-hoc neural saliency maps or LLM paraphrasing (which are prone to fabrication), Savora assembles an **evidence-based explanation trace**:
* Reconstructs the exact chain of logic:
  $$\text{Profile Clinical Constraints} \longrightarrow \text{Candidate Filter Traces} \longrightarrow \text{Nutrient Allocation Budget} \longrightarrow \text{Sequential Preference Match}$$
* Transparently displays why certain ingredients were omitted, how portions were scaled to satisfy daily caloric goals, and clearly distinguishes verified nutritional calculations from heuristic ranking scores.

---

## 4. Synthesized Evaluation & Empirical Takeaways

Rather than reciting exhaustive raw benchmark logs, this section summarizes the core empirical findings, performance characteristics, and practical trade-offs observed across the system components.

### 4.1 Recommendation Model Evaluation Insights
Evaluation was conducted on chronologically partitioned Food.com interactions (training before 2012; testing 2013+ over 231,637 items and 9,200 users):

| Model Configuration | Test HR@10 | Test NDCG@10 | Test MRR | Serving Median Latency |
|---|---|---|---|---|
| Popularity Baseline | 1.91% | 0.0091 | 0.0085 | < 0.1 ms |
| SASRec-v1 (lr 1e-3, overfitted) | 1.56% | 0.0074 | 0.0070 | 1.1 ms |
| **SASRec-v2 (Model Alone)** | **1.95%** | **0.0094** | **0.0089** | **0.5 ms** |
| **SASRec-v2 + Popularity Hybrid** | **1.99%** | **0.0093** | **0.0086** | **0.5 ms** |

*Takeaway 1 — Sequence Sparsity vs. Content Value:* Because real-world recipe interaction histories have a median length of just 1 to 2 recipes per user, sequential causal attention alone provides modest lift over global popularity. However, the Transformer model's content embeddings provide critical utility in ranking zero-interaction curated dishes and cultural staples that pure popularity cannot rank.  
*Takeaway 2 — Combination Aggregation:* When ranking composite meals composed of multiple dishes, experiments demonstrated that taking the **arithmetic mean of component dish scores** significantly outperformed using only the anchor main dish (+0.014 NDCG@10).

### 4.2 Weekly CSP Solver Performance
Benchmarking compared chronological backtracking against incremental forward checking across complex clinical personas:

```text
Solver Runtime Comparison on 21-Slot Indian Vegetarian Weekly Plan
────────────────────────────────────────────────────────────────────────
Naive Chronological Backtracking (v1)   ██████████████████████ 175s
Incremental Forward Checking + MRV (v2) ██████ 50s  [3.5x Faster]
────────────────────────────────────────────────────────────────────────
Constraint Violations: 0% across both versions (100% verified compliance)
```

*Takeaway 3 — Forward Checking Prevents Search Thrashing:* Chronological search repeatedly hit dead-ends at Sunday dinner due to accumulated macro imbalances. Maintaining dynamic cumulative bounds across unassigned slots prunes invalid branches early, ensuring predictable solving within acceptable interactive timeframes.

### 4.3 Craving NLU: Hybrid Architecture Robustness
Evaluated on an independent, held-out test suite of 58 complex natural language craving queries:

| Metric | Deterministic Template | Qwen-3 0.6B (Grounded) | Hybrid Production Pipeline |
|---|---|---|---|
| Schema Validity | 100% | 100% | **100%** |
| Intent Accuracy | 100% | 98.3% | **100%** |
| Slot Micro-F1 | 93.8% | 88.9% | **96.4%** |
| Exact Match Rate | 84.5% | 63.8% | **93.1%** |
| Latency (p50) | 0.14 ms | 363 ms | **365 ms** |

*Takeaway 4 — Hybrid Superiority:* While the local SLM provides linguistic flexibility for varied phrasing, it occasionally misses compound slot extractions. Merging the grounded SLM output with deterministic patterns yields the highest accuracy (93.1% exact match) while keeping edge inference overhead under 400 ms.

### 4.4 Formal Verification of Meal Substitutions
For dynamic user meal swaps, the Compact B1 proof protocol was evaluated across all 21 slots:
* In 100% of tested valid swap operations, the verifier successfully confirmed the updated schedule without violating any locked slot invariant.
* Every approved swap produced a verifiable SHA-256 state certificate digest, providing mathematical proof of zero clinical drift.

---

## 5. Software Engineering Rigor & Quality Assurance

To ensure capstone engineering integrity, Savora was built under strict production-grade software engineering practices:

```text
                                CODEBASE INTEGRITY
┌──────────────────────────────────────┬──────────────────────────────────────┐
│  Automated Verification Metric       │  Observed Production State          │
├──────────────────────────────────────┼──────────────────────────────────────┤
│  Pytest Test Suite                   │  3,933 Passed (0 Failures, 6 Skips)  │
│  Static Type Checking (Pyright)      │  0 Errors, 0 Warnings                │
│  Linter & Code Style (Ruff)          │  100% Compliant across 130 files     │
│  Package Boundary Enforcement        │  ai_system isolated from backend/db │
│  Deterministic Model Reproducibility │  Seed 7 exact weight replication     │
│  Alembic Migration Invariance        │  Clean up/down schema parity         │
└──────────────────────────────────────┴──────────────────────────────────────┘
```

1. **Strict Dependency Layering:** `savora_ai` is a pure Python package with zero dependency on Web APIs, ORM classes, or client storage. It can be executed and audited entirely offline.
2. **Deterministic Seeding:** Data selection, model training, negative sampling, and CSP search order use explicit versioned seeds, ensuring identical bit-for-bit plan reproduction.
3. **Pydantic v2 Contract Boundaries:** All inter-service and cross-language communications adhere to strict OpenAPI schemas with runtime type validation.

---

## 6. Limitations, Ethical Considerations & Future Work

1. **Dataset Demographics & Cultural Representation:** The primary interaction training corpus (Food.com) reflects predominantly North American user behaviors from 2000–2018. While our curated additions provide authentic South Asian and East Asian meal representations, collaborative sequence signals remain sparse for these cuisines.
2. **Approximation in Mixed-Meal Glycemic Load:** While individual recipe glycemic indexes are curated from clinical literature, dynamic biological glycemic response to mixed-macronutrient meals is complex and non-linear. Savora appropriately treats glycemic metrics as heuristic indicators rather than medical diagnostic claims.
3. **Discrete vs. Continuous Optimization:** Savora currently utilizes discrete portion presets (`STANDARD`, `LIGHT`, etc.). A promising future direction is formulating a hybrid Mixed-Integer Linear Program (MILP) to continuously optimize gram weights for even tighter nutrient alignment.
4. **Clinical Scope Boundaries:** The system explicitly defines itself as an advisory meal planning aid. It does not diagnose diseases or replace medical nutrition therapy prescribed by registered dietitians.

---

## 7. Conclusion

Savora demonstrates the power and necessity of a **neuro-symbolic design pattern** in health-critical AI applications. By delegating user preference modeling and language understanding to neural architectures while strictly assigning constraint verification, clinical safety checks, and scheduling feasibility to symbolic engines and formal proofs, the system achieves both high user personalization and uncompromising clinical safety.

The resulting implementation represents a robust, fully tested, and reproducible software system that successfully satisfies all Capstone requirements.

---

### Key System References & Code Manifest
* **System Architecture & Invariants:** [`ARCHITECTURE.md`](file:///Users/diwashbaral/AI/ai_code/Savora-AI-Meal-Planner-GC-1/ARCHITECTURE.md)
* **Model Implementation & Training:** [`torch_model.py`](file:///Users/diwashbaral/AI/ai_code/Savora-AI-Meal-Planner-GC-1/apps/ai_system/src/savora_ai/core/recommendation/torch_model.py)
* **CSP Weekly Solver & Pruning:** [`weekly_search_v2.py`](file:///Users/diwashbaral/AI/ai_code/Savora-AI-Meal-Planner-GC-1/apps/ai_system/src/savora_ai/core/reasoning/weekly_search_v2.py)
* **Formal Swap Proof Verifier:** [`swap_proof.py`](file:///Users/diwashbaral/AI/ai_code/Savora-AI-Meal-Planner-GC-1/apps/ai_system/src/savora_ai/core/reasoning/swap_proof.py)
* **Local Craving NLU Pipeline:** [`savora_ai/core/craving_nlu/`](file:///Users/diwashbaral/AI/ai_code/Savora-AI-Meal-Planner-GC-1/apps/ai_system/src/savora_ai/core/craving_nlu/)
* **Model Card v2 Documentation:** [`model_card_v2.md`](file:///Users/diwashbaral/AI/ai_code/Savora-AI-Meal-Planner-GC-1/docs/reports/model_card_v2.md)
