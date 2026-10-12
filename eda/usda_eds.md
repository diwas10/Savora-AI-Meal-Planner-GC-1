# USDA FoodData Central — Exploratory Data Analysis Summary

## 1. Dataset Overview

The USDA dataset used in this project is based on USDA FoodData Central data.

Unlike Food.com, which mainly provides complete recipes, ingredients, tags, ratings and user interactions, the USDA dataset is primarily useful as a structured nutritional reference source.

For this project, USDA can provide:

- Standardized food identifiers
- Food descriptions
- Food categories
- Nutrient definitions
- Nutrient values
- Measurement units
- Portion-to-gram conversion information
- Foundation Food records
- More reliable nutrient reference information for individual foods/ingredients

The EDA shows that the complete USDA download contains:

- 87,990 food records
- 477 nutrient definitions
- 170,469 food–nutrient records
- 28 food categories
- 395 USDA Foundation Foods
- 10,951 food-portion records
- 3,066 food-component records

However, not every table or every USDA food record is equally useful for the current GC1 meal-planning system.

---

# 2. Files Available in the USDA Dataset

The notebook identified the following files:

- `acquisition_samples.csv`
- `agricultural_samples.csv`
- `Download API Field Descriptions.xlsx`
- `food.csv`
- `food_attribute.csv`
- `food_attribute_type.csv`
- `food_calorie_conversion_factor.csv`
- `food_category.csv`
- `food_component.csv`
- `food_nutrient.csv`
- `food_nutrient_conversion_factor.csv`
- `food_portion.csv`
- `food_protein_conversion_factor.csv`
- `food_update_log_entry.csv`
- `foundation_food.csv`
- `input_food.csv`
- `lab_method.csv`
- `lab_method_code.csv`
- `lab_method_nutrient.csv`
- `market_acquisition.csv`
- `measure_unit.csv`
- `nutrient.csv`
- `sample_food.csv`
- `sub_sample_food.csv`
- `sub_sample_result.csv`

The largest files observed in the EDA include:

| File | Approximate Size |
|---|---:|
| `food_nutrient.csv` | 9.62 MB |
| `food.csv` | 6.89 MB |
| `sub_sample_result.csv` | 5.05 MB |
| `food_update_log_entry.csv` | 4.99 MB |
| `sub_sample_food.csv` | 1.41 MB |
| `market_acquisition.csv` | 0.87 MB |
| `food_attribute.csv` | 0.72 MB |
| `food_portion.csv` | 0.68 MB |

For the GC1 application, only a subset of these files is likely to be necessary.

---

# 3. Most Important USDA Files for GC1

The most useful files identified through the EDA are:

### Core files

1. `food.csv`
2. `food_nutrient.csv`
3. `nutrient.csv`
4. `foundation_food.csv`

### Supporting files

5. `food_category.csv`
6. `food_portion.csv`
7. `measure_unit.csv`

These seven files contain almost all of the USDA information directly relevant to the current nutritional recommendation pipeline.

Other USDA CSV files are mainly related to:

- laboratory methodology,
- sampling,
- acquisition,
- update logs,
- nutrient calculation factors,
- experimental sub-samples,
- food components,

and are not essential for the first version of the GC1 system.

---

# 4. `food.csv`

## Purpose

`food.csv` acts as the main USDA food master table.

It connects the USDA food identifier to:

- food name/description,
- food type,
- food category,
- publication date.

---

## Dataset Size

Shape:

- 87,990 rows
- 5 columns

Columns:

- `fdc_id`
- `data_type`
- `description`
- `food_category_id`
- `publication_date`

---

# 5. `fdc_id`

`fdc_id` is the unique USDA FoodData Central identifier.

The EDA found:

- Total food records: 87,990
- Unique FDC IDs: 87,990
- Duplicate FDC IDs: 0

Therefore:

`fdc_id`

can safely be used as the primary food identifier when connecting USDA tables.

For example:

`food.csv`

can connect to:

`food_nutrient.csv`

through:

`fdc_id`

---

# 6. Food Description

The `description` field contains the food name or food description.

Examples observed include:

- Hummus
- Hummus, commercial
- Tomatoes, grape, raw
- Kale, raw
- Cheese, cheddar
- Kiwifruit, green, raw
- Frankfurter, beef, unheated
- Nuts, almonds, dry roasted, with salt added

Only:

- 8 descriptions are missing

This represents approximately:

- 0.009% missing values

Therefore, food descriptions are almost completely available.

The food description is especially important for the project because it can be used when attempting to match Food.com ingredients to corresponding USDA foods.

For example:

Food.com ingredient:

`tomato`

could potentially be matched against USDA descriptions such as:

`Tomatoes, grape, raw`

The exact matching strategy is not implemented in this EDA, but `description` is the natural USDA text field for such matching.

---

# 7. Food Description Length

The EDA examined the length of USDA food descriptions.

Statistics:

- Mean length: approximately 33.7 characters
- Median: 31 characters
- 25th percentile: 20
- 75th percentile: 42
- Minimum: 0
- Maximum: 128 characters

This shows that USDA descriptions are generally short structured food descriptions rather than long natural-language text.

This is useful for ingredient matching because the descriptions often encode characteristics such as:

- food type,
- preparation state,
- cooking state,
- product form,
- salt status,
- processing method.

Example:

`Beans, snap, green, canned, regular pack, drained solids`

contains substantially more information than simply:

`green beans`.

---

# 8. `data_type`

The `food.csv` table contains a `data_type` column.

The dataset includes different types of USDA records, rather than every row representing the same level of food information.

Examples visible in the notebook include:

- `sample_food`
- `market_acquisition`
- `sub_sample_food`
- `foundation_food`

This distinction becomes important later in the EDA.

The notebook initially analyzed nutritional coverage across the entire USDA dataset, but many of these rows correspond to intermediate or experimental sampling records.

Therefore, the later analysis isolates USDA **Foundation Foods**, which are more appropriate for use as direct food-level reference records.

---

# 9. Missing Values in `food.csv`

The EDA found:

| Column | Missing | Percentage |
|---|---:|---:|
| `food_category_id` | 3,811 | 4.33% |
| `description` | 8 | 0.009% |
| `fdc_id` | 0 | 0% |
| `data_type` | 0 | 0% |
| `publication_date` | 0 | 0% |

The core identifiers are therefore complete.

Food categories have some missing values, but this does not prevent food–nutrient linking.

---

# 10. Duplicate Analysis

The EDA found:

- 0 duplicated rows
- 0 duplicated `fdc_id` values

This indicates strong identifier integrity in the master food table.

---

# 11. `food_category.csv`

## Purpose

`food_category.csv` provides broad USDA food categories.

Shape:

- 28 rows
- 3 columns

Columns:

- `id`
- `code`
- `description`

Example categories include:

- Dairy and Egg Products
- Spices and Herbs
- Baby Foods
- Fats and Oils
- Poultry Products

There are no missing values in this file.

---

# 12. Why Food Categories Are Useful

`food.csv` contains:

`food_category_id`

while `food_category.csv` provides the corresponding category description.

The relationship is:

`food.food_category_id`

→

`food_category.id`

This means foods can be classified into broader groups.

For the GC1 project, food categories could support:

- food-type classification,
- filtering,
- ingredient matching,
- candidate disambiguation.

For example, if a Food.com ingredient is:

`chicken breast`

a USDA match belonging to a poultry-related category may be more plausible than one from an unrelated food category.

However, food categories are supporting metadata rather than the main nutritional source.

---

# 13. `nutrient.csv`

## Purpose

`nutrient.csv` defines the nutrients used throughout USDA FoodData Central.

Shape:

- 477 rows
- 5 columns

Columns:

- `id`
- `name`
- `unit_name`
- `nutrient_nbr`
- `rank`

Examples include:

- Protein
- Total lipid (fat)
- Carbohydrate, by difference
- Energy
- Sodium
- Fiber
- Sugars
- Fatty acids

---

# 14. Why `nutrient.csv` Is Important

`food_nutrient.csv` stores nutrient values using numeric `nutrient_id` values.

For example:

`nutrient_id = 1003`

does not itself explain the nutrient.

`nutrient.csv` tells us that:

`1003 = Protein`

Therefore, `nutrient.csv` acts as a nutrient dictionary.

The relationship is:

`food_nutrient.nutrient_id`

→

`nutrient.id`

Without this mapping, nutrient values cannot easily be interpreted.

---

# 15. Important Nutrients Selected for GC1

The notebook selected eight nutrients relevant to the meal-planning system.

| Project Field | USDA Nutrient ID | USDA Name | Unit |
|---|---:|---|---|
| Calories | 1008 | Energy | KCAL |
| Protein | 1003 | Protein | G |
| Carbohydrates | 1005 | Carbohydrate, by difference | G |
| Total Fat | 1004 | Total lipid (fat) | G |
| Saturated Fat | 1258 | Fatty acids, total saturated | G |
| Fibre | 1079 | Fiber, total dietary | G |
| Sugar | 1063 | Sugars, Total | G |
| Sodium | 1093 | Sodium, Na | MG |

These eight nutrients were selected because they align with the major nutrition variables needed by the GC1 meal-planning system.

---

# 16. Why Explicit Nutrient IDs Matter

The EDA shows that USDA contains multiple nutrient definitions that may appear similar.

For example, energy includes:

- Energy
- Energy in kJ
- Energy calculated using Atwater General Factors
- Energy calculated using Atwater Specific Factors

Protein includes:

- Protein
- Adjusted Protein

Carbohydrate includes:

- Carbohydrate, by difference
- Carbohydrate, by summation
- Carbohydrate, other
- Carbohydrates

Fibre includes:

- Fiber, crude
- Fiber, total dietary
- Fiber, soluble
- Fiber, insoluble
- several additional dietary fibre definitions

Sugar includes:

- Sugars, Total
- Total Sugars
- Added Sugars
- Intrinsic Sugars
- Reducing Sugars

Therefore, the notebook does not simply search for any nutrient containing a word such as "sugar" or "carbohydrate".

It explicitly selects fixed USDA nutrient IDs.

This avoids accidentally mixing different nutrient definitions.

---

# 17. Archived Nutrients

The nutrient table includes fields explicitly marked:

`DO NOT USE - Archived`

Examples include:

- Fiber, crude
- Fiber, neutral detergent

The notebook therefore correctly selects:

`Fiber, total dietary`

with nutrient ID:

`1079`

rather than using archived fibre variables.

---

# 18. `food_nutrient.csv`

## Purpose

This is the main table containing nutrient measurements for USDA foods.

Shape:

- 170,469 rows
- 11 columns

Columns:

- `id`
- `fdc_id`
- `nutrient_id`
- `amount`
- `data_points`
- `derivation_id`
- `min`
- `max`
- `median`
- `footnote`
- `min_year_acquired`

---

# 19. Core Relationship in USDA Data

The most important relationship is:

`food.csv`

`fdc_id`

↓

`food_nutrient.csv`

`fdc_id + nutrient_id + amount`

↓

`nutrient.csv`

`nutrient_id → nutrient name + unit`

In simple terms:

**Food → Nutrient ID → Nutrient Definition → Nutrient Amount**

Example conceptually:

`Tomato`

→ `nutrient_id = 1093`

→ `Sodium`

→ `6 mg`

This relationship is the foundation of the nutritional validation layer.

---

# 20. Food-Nutrient Coverage

The complete `food_nutrient.csv` contains nutrient information for:

- 76,036 unique food IDs

There are:

- 235 unique nutrient IDs used in `food_nutrient.csv`

Of these:

- 234 nutrient IDs were found in `nutrient.csv`
- 1 nutrient ID did not match the nutrient definition table

All food IDs used in `food_nutrient.csv` were successfully found in `food.csv`.

Therefore:

- Food ID coverage = 100%

This indicates that food–nutrient relationships can be joined reliably through `fdc_id`.

---

# 21. Missing Values in `food_nutrient.csv`

Missing-value analysis found:

| Column | Missing % |
|---|---:|
| `footnote` | 99.99% |
| `min` | 89.69% |
| `max` | 89.69% |
| `median` | 89.33% |
| `min_year_acquired` | 81.05% |
| `data_points` | 2.14% |
| `derivation_id` | 0.25% |
| `amount` | 0.019% |

The main fields required by this project are:

- `fdc_id`
- `nutrient_id`
- `amount`

These are substantially more complete than the optional statistical metadata.

Therefore, fields such as:

- footnotes,
- min,
- max,
- median,

are not necessary for the basic GC1 nutrition pipeline.

---

# 22. Initial Eight-Nutrient Extraction

The notebook selects only the eight required nutrients from `food_nutrient.csv`.

This produces:

- 14,272 nutrient rows
- representing 10,664 USDA food records

The nutrient data is then converted from long format into wide format.

Original form:

`fdc_id | nutrient_id | amount`

becomes approximately:

`fdc_id | calories | protein | carbohydrates | total_fat | saturated_fat | fibre | sugar | sodium`

The resulting table initially has:

- 10,664 food records
- 12 total columns after joining food metadata

---

# 23. Initial USDA Nutrition Table

The generated table contains:

- `fdc_id`
- `description`
- `data_type`
- `food_category_id`
- `calories`
- `protein`
- `carbohydrates`
- `total_fat`
- `saturated_fat`
- `fibre`
- `sugar`
- `sodium`

This structure is highly convenient for downstream processing because each food becomes a single row.

---

# 24. Important Finding — General USDA Nutrient Coverage Is Sparse

When the notebook calculated coverage of the selected nutrients across all 87,990 USDA food records, the coverage was surprisingly low.

| Nutrient | Foods | Coverage |
|---|---:|---:|
| Total fat | 4,756 | 5.41% |
| Sodium | 3,856 | 4.38% |
| Fibre | 2,472 | 2.81% |
| Protein | 1,410 | 1.60% |
| Saturated fat | 986 | 1.12% |
| Carbohydrates | 377 | 0.43% |
| Sugar | 280 | 0.32% |
| Calories | 135 | 0.15% |

This does **not** mean that USDA nutrition data as a whole is generally unusable.

The notebook reveals that the download contains many intermediate records such as:

- sample foods,
- market acquisitions,
- sub-sample foods,

and nutrient observations may be distributed among these records.

Therefore, directly treating all 87,990 rows in `food.csv` as complete normal food records creates misleadingly sparse nutrition coverage.

This motivates the later Foundation Food analysis.

---

# 25. Missingness in the Initial Nutrition Table

For the 10,664-food nutrition table:

| Nutrient | Missing % |
|---|---:|
| Calories | 98.73% |
| Protein | 86.78% |
| Carbohydrates | 96.46% |
| Total fat | 55.40% |
| Saturated fat | 90.75% |
| Fibre | 76.82% |
| Sugar | 97.37% |
| Sodium | 63.84% |

Therefore, this broad table should **not simply be treated as a complete nutritional database** for the GC1 system.

The EDA correctly continues by isolating a more useful subset.

---

# 26. `foundation_food.csv`

## Purpose

The notebook then investigates USDA Foundation Foods separately.

Foundation Food shape:

- 395 rows
- 3 columns

Columns:

- `fdc_id`
- `NDB_number`
- `footnote`

There are:

- 395 records
- 395 unique FDC IDs

Therefore, there are no duplicate Foundation Food IDs.

---

# 27. Foundation Food Coverage in `food.csv`

All Foundation Food IDs were successfully found in `food.csv`.

Results:

- Foundation IDs: 395
- IDs matching `food.csv`: 395
- Coverage: 100%

All corresponding records in `food.csv` have:

`data_type = foundation_food`

This confirms that the Foundation Food table connects correctly to the main USDA food master table.

---

# 28. Examples of Foundation Foods

Examples visible in the EDA include:

- Hummus, commercial
- Tomatoes, grape, raw
- Beans, snap, green, canned
- Frankfurter, beef
- Almonds, dry roasted
- Kale, raw
- Egg, whole
- Parmesan cheese
- Grapefruit juice
- Peaches
- Sunflower seeds
- Mustard
- Kiwifruit
- Nectarines
- Cheddar cheese
- Mozzarella cheese

These are much closer to the kinds of individual foods/ingredients needed for ingredient-level nutritional reference.

---

# 29. Foundation Foods and Nutrient Data

All 395 Foundation Foods have nutrient records in `food_nutrient.csv`.

Results:

- Foundation nutrient rows: 17,008
- Foundation Foods with nutrient records: 395

When restricting those records to the selected eight nutrients:

- Required nutrient observations: 1,931
- Foundation Foods represented: 395

Therefore, every Foundation Food has at least one of the eight selected nutritional variables.

---

# 30. Foundation Food Nutrient Coverage

Coverage is considerably better than when the entire USDA table is treated uniformly.

| Nutrient | Foundation Foods | Coverage |
|---|---:|---:|
| Protein | 353 | 89.37% |
| Sodium | 349 | 88.35% |
| Total fat | 341 | 86.33% |
| Carbohydrates | 322 | 81.52% |
| Fibre | 198 | 50.13% |
| Sugar | 149 | 37.72% |
| Saturated fat | 124 | 31.39% |
| Calories | 95 | 24.05% |

This is an important EDA result.

Protein, sodium, fat and carbohydrates have strong coverage within the Foundation Food subset.

Fibre, sugar, saturated fat and especially calories remain incomplete.

---

# 31. Final Foundation Nutrition Table

The notebook creates a wide-format Foundation Food nutrition table.

Shape:

- 395 rows
- 12 columns

Columns:

- `fdc_id`
- `description`
- `data_type`
- `food_category_id`
- `calories`
- `protein`
- `carbohydrates`
- `total_fat`
- `saturated_fat`
- `fibre`
- `sugar`
- `sodium`

Example:

`Hummus, commercial`

contains values such as:

- Calories: 229 kcal
- Protein: 7.35 g
- Carbohydrates: 14.90 g
- Total fat: 17.10 g
- Saturated fat: 2.22 g
- Fibre: 5.4 g
- Sugar: 0.34 g
- Sodium: 438 mg

This represents the most immediately useful table generated by the USDA EDA.

---

# 32. Missing Values in Foundation Nutrition Data

The final Foundation Food table still contains missing nutritional values.

| Nutrient | Missing | Missing % |
|---|---:|---:|
| Calories | 300 | 75.95% |
| Protein | 42 | 10.63% |
| Carbohydrates | 73 | 18.48% |
| Total fat | 54 | 13.67% |
| Saturated fat | 271 | 68.61% |
| Fibre | 197 | 49.87% |
| Sugar | 246 | 62.28% |
| Sodium | 46 | 11.65% |

Therefore, USDA Foundation Foods are useful, but the selected download still does not provide all eight nutrients for every food.

This must be handled carefully rather than automatically filling missing nutrition values with zero.

A missing nutrient value means:

**the value is unavailable in the current table**

and does not automatically mean:

**the food contains zero of that nutrient.**

---

# 33. Foundation Nutrition Statistics

The EDA reports the following statistics.

### Calories

Available values:

- 95 foods

Mean:

- 210.52 kcal

Median:

- 156 kcal

Range:

- 12 to 833 kcal

---

### Protein

Available values:

- 353 foods

Mean:

- 10.39 g

Median:

- 7.38 g

Maximum:

- 79.9 g

---

### Carbohydrates

Available values:

- 322 foods

Mean:

- 18.69 g

Median:

- approximately 7.20 g

Maximum:

- 99.6 g

---

### Total Fat

Available values:

- 341 foods

Mean:

- 8.67 g

Median:

- 1.31 g

Maximum:

- 99.1 g

---

### Saturated Fat

Available values:

- 124 foods

Mean:

- 6.80 g

Median:

- approximately 3.24 g

Maximum:

- 82.5 g

---

### Fibre

Available values:

- 198 foods

Mean:

- 4.06 g

Median:

- approximately 3.00 g

Maximum:

- 34.95 g

---

### Sugar

Available values:

- 149 foods

Mean:

- 8.44 g

Median:

- 4.31 g

Maximum:

- 99.8 g

---

### Sodium

Available values:

- 349 foods

Mean:

- approximately 277.6 mg

Median:

- 20 mg

Maximum:

- 38,700 mg

The very large sodium maximum indicates that nutritional distributions contain extreme values and should be handled carefully.

---

# 34. Negative Nutrient Values

The notebook explicitly checks for negative nutritional values.

Results:

- Calories: 0 negative values
- Protein: 0
- Total fat: 0
- Saturated fat: 0
- Fibre: 0
- Sugar: 0
- Sodium: 0
- Carbohydrates: 10 negative values

Examples include:

- Chicken drumstick
- Chicken thigh
- Chicken wing
- Chicken breast
- Ground lamb
- Ground bison
- Pork chop
- Pork belly
- Halibut
- Tuna

The negative carbohydrate values are small, for example approximately:

- -0.06
- -0.17
- -0.48
- -0.71

These values should not automatically be interpreted as physically negative carbohydrate content.

They indicate that additional preprocessing/validation is required before strict nutrition constraints are applied.

---

# 35. `food_portion.csv`

## Purpose

This file provides portion information and gram equivalents.

Shape:

- 10,951 rows
- 11 columns

Columns:

- `id`
- `fdc_id`
- `seq_num`
- `amount`
- `measure_unit_id`
- `portion_description`
- `modifier`
- `gram_weight`
- `data_points`
- `footnote`
- `min_year_acquired`

The most relevant fields for GC1 are:

- `fdc_id`
- `amount`
- `measure_unit_id`
- `portion_description`
- `modifier`
- `gram_weight`

---

# 36. Why Portion Information Is Useful

Nutritional databases frequently express nutrients relative to a standard food quantity, while recipes use household units such as:

- cup
- tablespoon
- teaspoon

Therefore, portion information can help convert:

`recipe quantity`

into:

`grams`

which can then be used to estimate nutrient contribution.

Conceptually:

`1 cup of ingredient`

↓

`food_portion.csv`

↓

`X grams`

↓

USDA nutrient values

↓

nutrients for that recipe quantity

This makes `food_portion.csv` potentially valuable when calculating more precise recipe nutrition.

---

# 37. Foundation Food Portion Coverage

For the 395 Foundation Foods:

- Foods with portion information: 83
- Coverage: approximately 21.01%
- Portion records: 123

All 123 Foundation Food portion records have valid gram weights.

There are:

- 0 missing gram weights
- 0 zero gram weights

Therefore, where portion data exists, its gram-weight field is complete.

However, only about one-fifth of the Foundation Foods have portion information in this table.

---

# 38. Foundation Portion Gram Weight Statistics

For the 123 Foundation portion records:

- Mean: 148.11 g
- Median: 127 g
- Minimum: 3.2 g
- 25th percentile: 34.85 g
- 75th percentile: 173.5 g
- Maximum: 814 g

This confirms that portion sizes vary substantially between foods and measurement types.

---

# 39. Portion Amount

The `amount` field statistics are:

- Mean: 4.35
- Median: 1
- 25th percentile: 1
- 75th percentile: 1
- Minimum: 0.2
- Maximum: 100

Most recorded portions therefore correspond to an amount of 1 unit.

---

# 40. Portion Descriptions and Modifiers

Most Foundation Food portion descriptions are missing:

- 122 of 123 records have no `portion_description`
- only one visible description is `shredded`

However, modifiers contain useful preparation/context information for some records.

Examples include:

- raw
- sifted
- cooked
- medium
- peeled
- drained
- slices with skin
- small
- large
- extra large
- liquid oil
- without skin
- with skin
- grated

These descriptors may help distinguish different physical forms of the same food.

---

# 41. `measure_unit.csv`

## Purpose

`measure_unit.csv` translates numerical measurement IDs into understandable units.

Columns:

- `id`
- `name`

Examples:

| ID | Unit |
|---:|---|
| 1000 | cup |
| 1001 | tablespoon |
| 1002 | teaspoon |
| 1003 | liter |
| 1004 | milliliter |

Foundation Food portion records use:

- 30 unique measurement units

Therefore, `measure_unit.csv` should be joined with `food_portion.csv` using:

`food_portion.measure_unit_id`

→

`measure_unit.id`

This allows the system to interpret a portion record as a real measurement.

---

# 42. Portion Conversion Data Flow

The relationship is:

`Food`

↓

`fdc_id`

↓

`food_portion.csv`

↓

`amount + measure_unit_id + gram_weight`

↓

`measure_unit.csv`

↓

human-readable measurement

Example conceptually:

`Tomato`

→ `1 cup`

→ `X grams`

This could later allow more accurate nutrient calculation for recipe ingredient quantities.

---

# 43. `food_component.csv`

The notebook also investigates:

`food_component.csv`

Shape:

- 3,066 rows
- 8 columns

Columns:

- `id`
- `fdc_id`
- `name`
- `pct_weight`
- `is_refuse`
- `gram_weight`
- `data_points`
- `min_year_acqured`

Example component names include:

- Bone and connective tissue
- External fat
- Handling loss
- Seam fat
- Separable Lean
- Total gram weight

---

# 44. Food Component Missingness

The EDA reveals an important problem:

`fdc_id` is missing for:

- all 3,066 rows
- 100%

Other missingness includes:

- `min_year_acqured`: 97.26%
- `pct_weight`: 72.21%

Since `fdc_id` is completely missing, this file cannot be connected to Foundation Food IDs in the current downloaded dataset.

The EDA confirms:

- Foundation Foods with component records: 0
- Foundation component records: 0
- Foundation component coverage: 0%

Therefore, `food_component.csv` is **not useful for the current MVP pipeline in its present form**.

---

# 45. Files That Are Most Useful for the GC1 Project

## Essential

### `food.csv`

Provides:

`fdc_id + food description + category + data type`

Use it as the USDA food master table.

---

### `food_nutrient.csv`

Provides:

`fdc_id + nutrient_id + nutrient amount`

This is the main nutritional value table.

---

### `nutrient.csv`

Provides:

`nutrient_id + nutrient name + unit`

Required to understand the nutrient IDs in `food_nutrient.csv`.

---

### `foundation_food.csv`

Provides the subset of USDA Foundation Foods.

It is useful for selecting more food-like reference records rather than treating experimental sub-sample records as normal food records.

---

# 46. Supporting Files

### `food_category.csv`

Useful for:

- food group information
- disambiguating ingredient matches
- candidate filtering

---

### `food_portion.csv`

Useful for:

- portion conversion
- converting household quantities to grams
- more accurate nutrient calculations

However, Foundation Food portion coverage is only about 21%.

---

### `measure_unit.csv`

Required to interpret the `measure_unit_id` used in `food_portion.csv`.

---

# 47. Files Not Required for the Initial GC1 MVP

Based on this EDA, the following files are not required for the basic nutritional validation pipeline:

- `acquisition_samples.csv`
- `agricultural_samples.csv`
- `food_attribute.csv`
- `food_attribute_type.csv`
- `food_calorie_conversion_factor.csv`
- `food_nutrient_conversion_factor.csv`
- `food_protein_conversion_factor.csv`
- `food_update_log_entry.csv`
- `input_food.csv`
- `lab_method.csv`
- `lab_method_code.csv`
- `lab_method_nutrient.csv`
- `market_acquisition.csv`
- `sample_food.csv`
- `sub_sample_food.csv`
- `sub_sample_result.csv`

`food_component.csv` was investigated, but because its `fdc_id` field is completely missing in this dataset, it cannot currently be connected to Foundation Foods.

These files may become useful for deeper USDA analysis, laboratory provenance, or nutrition derivation, but they are unnecessary for the first GC1 recommendation pipeline.

---

# 48. Recommended USDA Files to Retain

For the current project, the practical set is:

```text
food.csv
food_nutrient.csv
nutrient.csv
foundation_food.csv
food_category.csv
food_portion.csv
measure_unit.csv
```

The absolute minimum nutritional core is:

```text
food.csv
food_nutrient.csv
nutrient.csv
foundation_food.csv
```

The other three are supporting tables.

---

# 49. Possible Processed USDA Table

The notebook already constructs a useful Foundation Food nutrition table with the structure:

```text
fdc_id
description
data_type
food_category_id
calories
protein
carbohydrates
total_fat
saturated_fat
fibre
sugar
sodium
```

This processed table would be considerably easier for the main system to consume than repeatedly joining the raw USDA CSV files during every recommendation request.

Conceptually, it could be saved as something like:

`usda_foundation_nutrition.csv`

or

`usda_foundation_nutrition.pkl`

The notebook does not show this file being saved, so this name is only a suggested processed output, not an existing file from the current EDA.

---

# 50. Suggested USDA Processing Flow

The main nutritional processing flow derived from the notebook is:

`foundation_food.csv`

↓

Select Foundation Food IDs

↓

`food.csv`

↓

Obtain food descriptions and categories

↓

`food_nutrient.csv`

↓

Extract nutrient measurements

↓

`nutrient.csv`

↓

Map nutrient IDs to selected nutrients

↓

Select:

- calories
- protein
- carbohydrates
- total fat
- saturated fat
- fibre
- sugar
- sodium

↓

Pivot into one row per food

↓

Create final USDA nutritional reference table

Optional:

`food_portion.csv`

+

`measure_unit.csv`

↓

portion → gram conversion

---

# 51. Role of USDA in the GC1 Architecture

USDA should not replace Food.com.

The two datasets serve different purposes.

## Food.com

Provides:

- complete recipes
- ingredient lists
- recipe tags
- recipe nutrition
- cooking information
- user ratings
- user preference history

Therefore, Food.com supplies the main:

**recipe candidate pool + recommendation information**

---

## USDA

Provides:

- standardized food records
- standardized nutrient definitions
- ingredient/food-level nutrient measurements
- food categories
- portion information
- measurement conversions

Therefore, USDA can serve primarily as a:

**nutritional reference and validation source**

---

# 52. Food.com + USDA Relationship

Conceptually, the project can use:

Food.com recipe

↓

Extract recipe ingredients

↓

Normalize ingredient names

↓

Match ingredient to USDA food description

↓

Retrieve USDA nutrient information

↓

Use USDA information as additional nutritional evidence/reference

↓

Apply dietary/nutritional constraints

↓

Rank/generate meal-plan candidates

This creates complementary use of the two datasets rather than treating them as duplicates.

---

# 53. Why USDA Is Important Even Though Food.com Already Contains Nutrition

Food.com already contains recipe-level nutrition fields.

However, USDA provides a separate structured source at the food/ingredient level.

This provides several advantages:

1. Food.com supplies recipe-level nutrition while USDA can supply ingredient/food-level nutrition.

2. USDA has standardized nutrient identifiers and measurement units.

3. USDA can help independently reference nutritional properties of ingredients.

4. USDA portion records can potentially support quantity-to-gram conversion.

5. USDA food categories can help disambiguate ingredient matching.

Therefore, USDA is complementary to Food.com rather than redundant.

---

# 54. Important Limitations Identified by the USDA EDA

The EDA identifies several limitations that should be explicitly considered.

### 1. Nutrient coverage is incomplete

Even among Foundation Foods, not every nutrient is present for every food.

For example:

- Protein coverage ≈ 89%
- Sodium ≈ 88%
- Total fat ≈ 86%
- Carbohydrates ≈ 82%
- Calories ≈ 24%

Therefore, missing values require careful handling.

---

### 2. Do not interpret missing as zero

If sugar is missing, for example, that does not necessarily mean:

`sugar = 0`

It means:

`the current USDA record does not contain that selected nutrient value`.

---

### 3. Portion coverage is limited

Only:

- 83 of 395 Foundation Foods

have portion data.

Coverage:

- approximately 21%

Therefore, USDA portion conversion cannot be assumed to exist for every ingredient.

---

### 4. USDA names will not exactly match Food.com ingredient names

Food.com might contain:

`tomatoes`

while USDA may contain:

`Tomatoes, grape, raw`

Therefore, direct exact-string matching will not always work.

Ingredient normalization or semantic/fuzzy matching will likely be needed.

---

### 5. Negative carbohydrate values exist

Ten Foundation Foods have small negative carbohydrate values.

These should be validated or corrected during preprocessing rather than blindly passed into strict constraint calculations.

---

### 6. Extreme nutrient values exist

For example, Foundation Food sodium reaches:

- 38,700 mg

The full extracted table reaches:

- 40,700 mg

These values should be examined in context before outlier removal because unusual foods may legitimately contain extremely high sodium.

---

### 7. `food_component.csv` cannot currently be linked

Its `fdc_id` column is 100% missing in the supplied data.

Therefore, it provides no usable Foundation Food relationship in the current EDA.

---

# 55. Main EDA Findings

The most important findings are:

1. USDA contains 87,990 food records with unique FDC IDs.

2. The nutrient dictionary contains 477 different nutrient definitions.

3. `food_nutrient.csv` contains 170,469 nutrient measurements.

4. Nutrient records cover 76,036 USDA food IDs.

5. Every food ID appearing in the nutrient table matches the master `food.csv` table.

6. The project selects eight nutrients:
   - calories
   - protein
   - carbohydrates
   - total fat
   - saturated fat
   - fibre
   - sugar
   - sodium.

7. Treating all 87,990 food records as equivalent produces very sparse selected-nutrient coverage because many USDA records represent sample/sub-sample data.

8. The notebook therefore isolates 395 Foundation Foods.

9. All 395 Foundation Foods occur in `food.csv`.

10. All 395 Foundation Foods have nutrient records.

11. Foundation Foods provide much stronger coverage for protein, sodium, fat and carbohydrates.

12. Some nutritional fields, particularly calories, saturated fat and sugar, remain incomplete.

13. USDA provides useful portion-to-gram information, but only around 21% of Foundation Foods have portion records in this dataset.

14. Food component information is unusable for the current joins because `fdc_id` is completely missing.

---

# 56. Final Recommended USDA Data Flow for GC1

```text
                    foundation_food.csv
                           │
                           │ fdc_id
                           ↓
                       food.csv
                           │
              ┌────────────┴────────────┐
              │                         │
              ↓                         ↓
      food_category.csv         food_nutrient.csv
                                        │
                                        │ nutrient_id
                                        ↓
                                  nutrient.csv
                                        │
                                        ↓
                        Select required nutrients
                                        │
                                        ↓
                   Foundation Nutrition Table
                                        │
                     ┌──────────────────┘
                     │
                     ↓
               GC1 nutrition layer
```

Optional portion conversion:

```text
food.csv
   │
   │ fdc_id
   ↓
food_portion.csv
   │
   │ measure_unit_id
   ↓
measure_unit.csv

→ household measurement to gram conversion
```

---

# 57. Final File Selection for the Project

## Definitely keep

```text
food.csv
food_nutrient.csv
nutrient.csv
foundation_food.csv
```

These four are the nutritional core.

## Useful supporting files

```text
food_category.csv
food_portion.csv
measure_unit.csv
```

These support classification and portion conversion.

## Not necessary for current MVP

The remaining acquisition, sampling, laboratory, conversion-factor and update-log tables can remain outside the main modelling pipeline unless later experimentation demonstrates a specific need for them.

---

# 58. Final USDA Contribution to GC1

The USDA component of the project can therefore be summarized as:

**Food Identification**

`food.csv`

+

**Reliable Nutrient Definitions**

`nutrient.csv`

+

**Nutrient Measurements**

`food_nutrient.csv`

+

**Reference Food Subset**

`foundation_food.csv`

+

**Optional Food Categories**

`food_category.csv`

+

**Optional Portion Conversion**

`food_portion.csv + measure_unit.csv`

↓

**Structured nutritional reference layer for GC1**

The key distinction is:

> **Food.com tells the system what recipes exist and what users may prefer; USDA provides structured food-level nutritional information that can be used as additional nutritional evidence and validation.**