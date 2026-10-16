# Food.com Dataset â€” Exploratory Data Analysis Summary

## 1. Dataset Overview

The Food.com dataset provides three main types of information required for the meal-planning/recommendation system:

1. Recipe information â€” ingredients, nutrition, preparation steps, cooking time, tags, etc.
2. User interaction information â€” ratings, reviews, users, recipes and timestamps.
3. Ingredient normalization information â€” mappings from different raw ingredient names to standardized ingredient representations.

The EDA shows that Food.com is a large dataset containing:

- 231,637 recipes
- 1,132,367 userâ€“recipe interactions
- 226,570 unique users
- 14,942 unique raw ingredient strings extracted from recipes
- 552 unique recipe tags

This makes Food.com useful as the main source of recipe content and historical user preference information.

---

# 2. Files Available in the Food.com Dataset

The notebook identified the following files:

| File | Purpose | Used in EDA? | Importance |
|---|---|---:|---|
| `RAW_recipes.csv` | Original recipe information | Yes | Essential |
| `RAW_interactions.csv` | User ratings and reviews | Yes | Essential |
| `ingr_map.pkl` | Ingredient normalization/mapping | Yes | Essential |
| `PP_recipes.csv` | Preprocessed/tokenized recipe representation | Yes | Supporting |
| `PP_users.csv` | Preprocessed user information | No detailed analysis | Not required for current MVP |
| `interactions_train.csv` | Predefined training interactions | Yes | Useful for model training |
| `interactions_validation.csv` | Validation interactions | Yes | Useful for model validation |
| `interactions_test.csv` | Testing interactions | Yes | Useful for final evaluation |

After EDA and preprocessing, three final files were generated:

- `recipes_final.pkl`
- `interactions_final.pkl`
- `ingredient_map_final.pkl`

These are explicitly identified in the notebook as the files to use for the MVP.

---

# 3. RAW_recipes.csv

## Dataset Size

Original shape:

- Rows: 231,637
- Columns: 12

Original columns:

- `name`
- `id`
- `minutes`
- `contributor_id`
- `submitted`
- `tags`
- `nutrition`
- `n_steps`
- `steps`
- `description`
- `ingredients`
- `n_ingredients`

Each row represents one Food.com recipe.

---

# 4. Important Recipe Fields

## `id`

Unique identifier for each recipe.

The EDA found:

- 231,637 recipes
- 231,637 unique recipe IDs
- 0 duplicate recipe IDs

Therefore, `id` can safely be used as the recipe identifier and later becomes `recipe_id`.

---

## `name`

Contains the recipe name.

There is only:

- 1 missing recipe name

There are 230,185 unique names among 231,636 non-null names.

Recipe names are useful mainly for displaying recommendations to users.

---

## `minutes`

Represents recipe preparation/cooking time.

Summary:

- Median: 40 minutes
- 25th percentile: 20 minutes
- 75th percentile: 65 minutes
- Minimum: 0
- Maximum: 2,147,483,647 minutes

The extremely large maximum causes the mean to become approximately 9,398 minutes, showing that this field contains severe outliers or erroneous values.

Therefore, the median and normal range are much more representative than the mean.

This field can later support constraints such as:

> "Recommend meals that can be prepared within 30 minutes."

---

# 5. Ingredients Analysis

The original `ingredients` field is stored as a string representation of a Python list.

Example:

`['winter squash', 'mexican seasoning', 'mixed spice', 'honey', 'butter', 'olive oil', 'salt']`

The notebook converts this into a real Python list called:

`ingredients_list`

This allows individual ingredients to be analyzed and processed.

---

## Number of Ingredients Per Recipe

Statistics:

- Mean: 9.05 ingredients
- Median: 9 ingredients
- 25th percentile: 6
- 75th percentile: 11
- Minimum: 1
- Maximum: 43

Therefore, a typical Food.com recipe contains roughly 9 ingredients.

The notebook also verifies that the parsed ingredient count exactly matches the existing `n_ingredients` column for all 231,637 recipes.

---

# 6. Unique Ingredients

After extracting ingredients from every recipe:

- Total unique raw ingredient strings: 14,942

Some of the most common ingredients are:

| Ingredient | Recipes |
|---|---:|
| Salt | 85,746 |
| Butter | 54,975 |
| Sugar | 44,535 |
| Onion | 39,065 |
| Water | 34,914 |
| Eggs | 33,761 |
| Olive oil | 32,822 |
| Flour | 26,266 |
| Milk | 25,786 |
| Garlic cloves | 25,748 |
| Pepper | 22,319 |
| Brown sugar | 18,655 |
| Garlic | 18,087 |
| All-purpose flour | 17,659 |
| Baking powder | 17,504 |

This analysis shows that the raw ingredient vocabulary contains multiple variations referring to similar ingredients.

For example:

- garlic
- garlic clove
- garlic cloves
- fresh garlic
- minced garlic cloves

This motivates ingredient normalization.

---

# 7. Ingredient Frequency Distribution

Across the 14,942 unique raw ingredient strings:

- Mean occurrence: 140.31 recipes
- Median occurrence: 5 recipes
- 75th percentile: 28 recipes
- Maximum occurrence: 85,746 recipes

This indicates a strong long-tail distribution.

A relatively small number of common ingredients appear in many recipes, while a very large number of ingredients occur only rarely.

This is important for recommendation because ingredient representations need to handle both common and rare ingredients.

---

# 8. Measurement / Numeric Ingredient Analysis

The notebook checks whether the ingredient strings contain measurement terminology.

Examples found include:

- `oz`
- `lb`
- `cup`
- `cups`
- `pound`
- `lbs`
- `gram`
- `ml`

It also found:

- 188 unique ingredient strings containing numeric values.

Examples include:

- `2% low-fat milk`
- `98% fat-free cream of mushroom soup`
- `10 bean soup mix`
- `12-inch pizza crust`
- `80% lean ground beef`

This is important because numbers inside ingredient names do not necessarily represent ingredient quantities. They can represent product characteristics such as fat percentage or size.

---

# 9. Recipe Tags

The `tags` column is also originally stored as a string representation of a list.

The notebook converts it into:

`tags_list`

The dataset contains:

- 552 unique tags.

The most frequent tags include:

| Tag | Number of Recipes |
|---|---:|
| preparation | 230,546 |
| time-to-make | 225,326 |
| course | 218,148 |
| main-ingredient | 170,446 |
| dietary | 165,091 |
| easy | 126,062 |
| occasion | 114,145 |
| cuisine | 91,165 |
| low-in-something | 85,776 |
| main-dish | 71,786 |
| equipment | 70,436 |
| 60-minutes-or-less | 69,990 |
| number-of-servings | 58,949 |
| meat | 56,042 |
| 30-minutes-or-less | 55,077 |
| vegetables | 53,814 |

Tags therefore provide useful semantic metadata for identifying recipe characteristics.

---

# 10. Dietary Information Available Through Tags

The Food.com tags contain several useful dietary categories.

Important dietary tags found include:

| Dietary Tag | Recipes |
|---|---:|
| low-sodium | 43,349 |
| low-carb | 42,189 |
| healthy | 40,340 |
| low-cholesterol | 36,743 |
| vegetarian | 35,651 |
| low-saturated-fat | 31,378 |
| healthy-2 | 26,619 |
| low-fat | 22,170 |
| vegan | 10,012 |
| very-low-carbs | 9,201 |
| high-protein | 7,209 |
| diabetic | 6,458 |

For selected dietary categories, the notebook calculated:

- Vegetarian: 35,651 recipes â€” 15.39%
- Vegan: 10,012 â€” 4.32%
- Low sodium: 43,349 â€” 18.71%
- Low carb: 42,189 â€” 18.21%
- Low cholesterol: 36,743 â€” 15.86%
- Low fat: 22,170 â€” 9.57%

These tags are useful for candidate filtering and recommendation features.

However, they are dataset-provided labels and should not automatically be treated as authoritative medical or dietary constraints without external validation.

---

# 11. Time-Related Tags

Food.com also contains useful preparation-time tags such as:

- `easy` â€” 126,062 recipes
- `60-minutes-or-less` â€” 69,990
- `30-minutes-or-less` â€” 55,077
- `4-hours-or-less` â€” 49,497
- `15-minutes-or-less` â€” 43,934

These can complement the numerical `minutes` column when filtering or ranking recipes based on time constraints.

---

# 12. Cuisine Information

Cuisine information is mainly encoded through tags.

The EDA identified:

- 68,631 recipes with an identified cuisine
- Approximately 29.63% of all recipes

The generic `cuisine` tag itself occurs in 91,165 recipes.

The dataset also contains an `indian` tag:

- Indian recipes: 2,708

However, the EDA did not find explicit:

- South Indian tags
- North Indian tags

Therefore, Food.com alone may not provide sufficiently fine-grained regional cuisine classification.

---

# 13. Nutrition Information

The original `nutrition` field is stored as a string containing seven values.

The notebook converts this field into a Python list and then separates it into seven nutrition variables:

1. Calories — kcal
2. Total fat — %DV, not grams
3. Sugar — %DV, not grams
4. Sodium — %DV, not milligrams
5. Protein — %DV, not grams
6. Saturated fat — %DV, not grams
7. Carbohydrates — %DV, not grams

Before applying physical-unit nutrition constraints, convert the %DV fields using validated dataset-specific daily-value references and verify the serving/reference quantity.

All 231,637 recipes contain nutrition vectors of length 7.

There are:

- 0 missing nutrition vectors
- 0 missing values after expanding the seven nutrient columns

This is a major strength of the Food.com dataset for the project.

---

# 14. Nutrition Statistics

### Calories

- Mean: 473.94
- Median: 313.4
- 25th percentile: 174.4
- 75th percentile: 519.7

The maximum is 434,360.2, indicating extreme outliers.

### Total Fat

- Mean: 36.08
- Median: 20

### Sugar

- Mean: 84.30
- Median: 25

### Sodium

- Mean: 30.15
- Median: 14

### Protein

- Mean: 34.68
- Median: 18

### Saturated Fat

- Mean: 45.59
- Median: 23

### Carbohydrates

- Mean: 15.56
- Median: 9

The notebook identifies substantial extreme values, so raw nutrition values should be checked carefully before being used for strict nutritional constraints.

---

# 15. Nutrition Outliers

Using the IQR method, the notebook identified:

- Calories: 15,737 outliers â€” 6.79%
- Total fat: 16,265 â€” 7.02%
- Sugar: 23,780 â€” 10.27%
- Sodium: 15,919 â€” 6.87%
- Protein: 9,141 â€” 3.95%
- Saturated fat: 16,462 â€” 7.11%
- Carbohydrates: 15,559 â€” 6.72%

Sugar has the highest proportion of IQR-defined outliers among the seven variables.

This indicates that nutrition values require validation or robust handling rather than blindly removing every statistical outlier, because some high values may correspond to genuinely large recipes.

---

# 16. Nutrition Correlations

Several strong correlations were found.

Important examples:

- Sugar â†” Carbohydrates: 0.981
- Calories â†” Carbohydrates: 0.904
- Total fat â†” Saturated fat: 0.871
- Calories â†” Sugar: 0.864
- Calories â†” Total fat: 0.600

These relationships are expected to create correlated nutritional features in downstream modelling.

---

# 17. Recipe Descriptions

The dataset contains descriptions for:

- 226,658 recipes

Missing descriptions:

- 4,979
- Approximately 2.15%

Therefore, descriptions are available for approximately 97.85% of recipes.

Descriptions could potentially provide additional textual information for semantic recipe representations, although they are not included in the final MVP recipe table created by this notebook.

---

# 18. PP_recipes.csv

`PP_recipes.csv` is a preprocessed representation of Food.com recipes.

Shape:

- 178,265 rows
- 8 columns

Columns:

- `id`
- `i`
- `name_tokens`
- `ingredient_tokens`
- `steps_tokens`
- `techniques`
- `calorie_level`
- `ingredient_ids`

There are:

- No missing values
- No duplicate rows

This file contains already-tokenized representations rather than the human-readable raw recipe information.

The notebook joins `PP_recipes.csv` with `RAW_recipes.csv` using `id`.

Result:

- 178,265 matched recipes

All 178,265 matched records contain non-empty `ingredient_ids`.

### Usefulness

`PP_recipes.csv` is useful for:

- ingredient IDs
- tokenized recipe information
- processed representations
- calorie-level information

However, the notebook's final MVP recipe table is primarily constructed from `RAW_recipes.csv`.

---

# 19. Ingredient Mapping â€” ingr_map.pkl

`ingr_map.pkl` contains the mapping between raw ingredient names and standardized ingredient representations.

Shape:

- 11,659 rows
- 7 columns

Columns:

- `raw_ingr`
- `raw_words`
- `processed`
- `len_proc`
- `replaced`
- `count`
- `id`

There are no missing values.

---

# 20. Ingredient Normalization

The ingredient mapping contains:

- 11,659 unique raw ingredients
- 9,035 unique processed ingredients
- 8,023 unique ingredient IDs

The transformation from raw to processed ingredient names reduces the vocabulary by:

- 22.51%

This is useful because multiple ingredient expressions can refer to essentially the same ingredient.

For example, variants of tomato, cream cheese, chicken broth and other ingredients can be consolidated.

One processed ingredient such as `diced tomato` has 27 raw variants.

---

# 21. Ingredient Mapping Coverage

Food.com recipes contain:

- 14,942 unique raw ingredients.

The ingredient map directly covers:

- 11,659 of these ingredients.

Coverage:

- 78.03%

Unmapped:

- 3,283 ingredients

Therefore, the ingredient mapping is highly useful but does not cover the complete Food.com ingredient vocabulary.

This is an important limitation.

Additional normalization or fallback matching may be needed for the remaining ingredients.

---

# 22. RAW_interactions.csv

This file stores user interactions with Food.com recipes.

Shape:

- 1,132,367 interactions
- 5 columns

Columns:

- `user_id`
- `recipe_id`
- `date`
- `rating`
- `review`

It contains:

- 226,570 unique users
- 231,637 unique recipes
- 1,132,367 interactions

There are:

- 0 duplicate rows
- 0 duplicate userâ€“recipe pairs

Only 169 reviews are missing, corresponding to approximately 0.015%.

---

# 23. Rating Distribution

Ratings range from 0 to 5.

Distribution:

| Rating | Interactions |
|---:|---:|
| 0 | 60,847 |
| 1 | 12,818 |
| 2 | 14,123 |
| 3 | 40,855 |
| 4 | 187,360 |
| 5 | 816,364 |

Overall:

- Mean rating: 4.41
- Median rating: 5

This shows that the interaction data is heavily skewed toward positive ratings.

---

# 24. Positive Interaction Definition

The notebook creates a binary variable:

`positive = 1 if rating >= 4`

Using this definition:

- Positive interactions: 1,003,724
- Negative/non-positive interactions: 128,643
- Positive rate: 88.64%
- Non-positive rate: 11.36%

Therefore, the recommendation data has a strong positive-class imbalance.

This must be considered during recommendation-model training and evaluation.

---

# 25. User Interaction Distribution

Interactions per user:

- Mean: 5.00
- Median: 1
- 75th percentile: 2
- Minimum: 1
- Maximum: 7,671

This means most users have very few interactions while a small number of users are extremely active.

This creates a classic long-tail/cold-start challenge.

---

# 26. Recipe Interaction Distribution

Interactions per recipe:

- Mean: 4.89
- Median: 2
- 75th percentile: 4
- Minimum: 1
- Maximum: 1,613

Again, this indicates a long-tail distribution.

Many recipes have very little interaction history while a small number are highly popular.

---

# 27. Interaction Matrix Sparsity

Potential userâ€“recipe combinations are extremely large compared with the observed interactions.

The calculated interaction sparsity is:

- 99.9978%

This means only a tiny fraction of possible userâ€“recipe combinations have observed interactions.

This is a major characteristic of the recommendation problem and makes relying purely on collaborative filtering difficult.

Recipe content such as ingredients, tags and nutrition can therefore be particularly useful alongside interaction history.

---

# 28. Review Information

There are:

- 1,132,198 non-empty reviews
- 169 empty reviews

Review length statistics:

- Mean: approximately 278 characters
- Median: 237 characters
- 25th percentile: 147
- 75th percentile: 358
- Maximum: 8,587 characters

The review text could potentially be used for sentiment or preference extraction, although it is not retained in the notebook's final MVP interaction table.

---

# 29. Date / Timestamp Information

`RAW_interactions.csv` contains a `date` field for each userâ€“recipe interaction.

The final interaction table retains this field.

It is useful for preserving the temporal sequence of user behaviour and can potentially support chronological analysis or time-aware train/test splitting.

The notebook does not derive more detailed temporal features from it at this stage.

---

# 30. Train, Validation and Test Interaction Files

The dataset also provides predefined interaction splits.

### interactions_train.csv

Shape:

- 698,901 rows
- 6 columns

### interactions_validation.csv

Shape:

- 7,023 rows
- 6 columns

### interactions_test.csv

Shape:

- 12,455 rows
- 6 columns

All three contain:

- `user_id`
- `recipe_id`
- `date`
- `rating`
- `u`
- `i`

Unique users:

- Train: 25,076
- Validation: 7,023
- Test: 12,455

Unique recipes:

- Train: 160,901
- Validation: 6,621
- Test: 11,695

User overlap:

- Train âˆ© Validation: 7,023
- Train âˆ© Test: 12,455
- Validation âˆ© Test: 5,839

These predefined files can be used when training and evaluating recommendation models.

---

# 31. Recipeâ€“Interaction Matching

A critical validation was performed between recipe IDs and interaction recipe IDs.

Results:

- Recipes in `RAW_recipes.csv`: 231,637
- Recipes referenced by interactions: 231,637
- Common recipe IDs: 231,637

Coverage:

- 100%

Similarly, all 1,132,367 interactions have a matching recipe in the recipe dataset.

This is a major data-quality advantage because no interaction records need to be removed because of missing recipe metadata.

---

# 32. Final Processed Recipe Table

The notebook constructs:

`recipes_final.pkl`

Shape:

- 231,637 rows
- 15 columns

Columns:

- `recipe_id`
- `name`
- `ingredients`
- `tags`
- `n_steps`
- `n_ingredients`
- `ingredients_list`
- `tags_list`
- `calories`
- `total_fat`
- `sugar`
- `sodium`
- `protein`
- `saturated_fat`
- `carbohydrates`

Only one missing value remains:

- one missing `name`

All important ingredient, tag and nutrition information is available.

### Main use

This should be the primary recipe-content table for the MVP.

It provides the information needed for:

- recipe identification
- ingredient matching
- dietary filtering
- nutrition constraints
- recipe ranking features
- meal-plan generation

---

# 33. Final Interaction Table

The notebook constructs:

`interactions_final.pkl`

Shape:

- 1,132,367 rows
- 5 columns

Columns:

- `user_id`
- `recipe_id`
- `rating`
- `date`
- `positive`

The `positive` feature is derived using:

`rating >= 4`

### Main use

This table provides historical user preference signals for recommendation/ranking.

It can be used to learn which recipes users are likely to prefer.

---

# 34. Final Ingredient Mapping Table

The notebook constructs:

`ingredient_map_final.pkl`

Shape:

- 11,659 rows
- 5 columns

Columns:

- `raw_ingr`
- `processed`
- `replaced`
- `count`
- `id`

It contains:

- 11,659 raw ingredients
- 9,035 processed ingredients
- 8,023 ingredient IDs

### Main use

This file supports ingredient normalization.

It helps convert different ingredient names or variations into more consistent representations before recommendation, matching or constraint checking.

---

# 35. Final MVP Files

The notebook explicitly identifies the following three processed files for the MVP:

### 1. `recipes_final.pkl`

Provides recipe content:

Recipe â†’ Ingredients + Tags + Nutrition + Recipe Metadata

### 2. `interactions_final.pkl`

Provides user preference information:

User â†’ Recipe â†’ Rating â†’ Positive/Negative Preference

### 3. `ingredient_map_final.pkl`

Provides ingredient normalization:

Raw Ingredient â†’ Processed/Standardized Ingredient

Together, these three files provide the core Food.com data needed for the recommendation pipeline.

---

# 36. Files That Are Supporting Rather Than Core

### `PP_recipes.csv`

Useful because it provides tokenized recipes and ingredient IDs, but it is not used as the final main recipe table.

### `PP_users.csv`

Present in the dataset directory but not meaningfully analyzed or included in the final MVP pipeline in this notebook.

### `interactions_train.csv`
### `interactions_validation.csv`
### `interactions_test.csv`

Useful for model training and evaluation, particularly if the provided Food.com split is retained.

They do not replace `interactions_final.pkl`, which provides the complete interaction history used in the final processed dataset.

---

# 37. Main EDA Findings

The Food.com EDA shows several important characteristics of the dataset:

1. The dataset is large, containing 231,637 recipes and over 1.13 million interactions.

2. Recipe metadata is highly complete. Only one recipe name and approximately 2.15% of descriptions are missing.

3. Nutrition data is available for every recipe and contains seven nutritional variables.

4. Nutrition values contain substantial extreme values/outliers, meaning robust preprocessing or validation will be important before applying nutritional constraints.

5. Recipes contain rich dietary and semantic tags such as vegetarian, vegan, low-sodium, low-carb and cuisine information.

6. Cuisine information is incomplete: only about 29.63% of recipes were assigned an identified cuisine in the notebook's cuisine extraction.

7. Ingredient vocabulary is highly varied, with 14,942 unique raw ingredient strings.

8. Ingredient normalization reduces vocabulary from 11,659 mapped raw ingredients to 9,035 processed ingredients, a 22.51% reduction.

9. The ingredient map directly covers approximately 78.03% of Food.com's unique raw ingredients, leaving 3,283 unmapped ingredient strings.

10. User ratings are strongly biased toward positive feedback: 88.64% of interactions have ratings of at least 4.

11. Userâ€“recipe interaction data is extremely sparse at 99.9978%.

12. Most users have very little interaction history: the median user has only one interaction.

13. All recipes referenced by interactions successfully match recipes in `RAW_recipes.csv`, providing 100% recipe-ID coverage.

---

# 38. Why Food.com Is Useful for the Project

Food.com is useful because it provides both sides of the recommendation problem.

### Recipe/content information

`recipes_final.pkl` provides:

Ingredients + Nutrition + Dietary Tags + Recipe Metadata

This helps determine whether a recipe is suitable for the user's requirements.

### User preference information

`interactions_final.pkl` provides:

User + Recipe + Rating + Timestamp

This provides historical preference signals for learning which suitable recipes a user may actually prefer.

### Ingredient normalization

`ingredient_map_final.pkl` provides:

Raw Ingredient â†’ Standardized Ingredient

This helps make ingredient matching more reliable.

Therefore, Food.com can provide the project's **recipe candidate pool and preference-learning data**, while other sources such as nutritional databases, dietary guidelines, and allergy knowledge can provide additional authoritative constraints and validation.

---

# 39. Important Limitations Identified by the EDA

The EDA also reveals several limitations that should be considered during system development:

- Nutrition contains extreme/outlier values.
- Food.com dietary tags are metadata labels rather than authoritative medical guidelines.
- Only around 29.63% of recipes received an identified cuisine in the notebook's cuisine analysis.
- Fine-grained categories such as South Indian and North Indian were not available as explicit tags.
- Ingredient mapping covers approximately 78% of unique raw ingredient strings rather than 100%.
- Ratings are heavily biased toward positive ratings.
- Interaction data is extremely sparse.
- Most users have very little historical interaction data.
- Some raw ingredient names contain product sizes, percentages and measurements, making normalization more difficult.
- Review text and recipe descriptions are available but are not included in the current final MVP tables.

---

# 40. Final Food.com Data Flow

The EDA can be summarized as:

`RAW_recipes.csv`

â†’ Parse ingredients and tags  
â†’ Extract nutrition variables  
â†’ Analyze dietary/cuisine metadata  
â†’ Clean/select useful recipe features  
â†’ `recipes_final.pkl`

`RAW_interactions.csv`

â†’ Analyze ratings/reviews/users  
â†’ Create positive interaction (`rating >= 4`)  
â†’ Match interactions with recipes  
â†’ `interactions_final.pkl`

`ingr_map.pkl`

â†’ Analyze raw/processed ingredient mappings  
â†’ Select useful normalization fields  
â†’ `ingredient_map_final.pkl`

Final Food.com MVP input:

**`recipes_final.pkl` + `interactions_final.pkl` + `ingredient_map_final.pkl`**

These three processed datasets form the Food.com component of the project's data pipeline.