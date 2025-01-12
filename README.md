# Meal Planner

Given a database of ingredients with macronutrients information and daily requirements, the program recommends optimal ingredients to use for meal planning. If an OpenAI account is available, it can also generate meal plans!

# Requirements

-   Python 3.10
-   Use `requirements.txt` to install required packages
-   OpenAI API key to generate meal plans (set value in `.env` - see `.env.example`)

# Usage

## Nutrients Data

Use `data/nutrients.csv` and update as needed.

-   Macronutrients information is from [USDA FoodData Central Search](https://fdc.nal.usda.gov/food-search)
-   Specify minimum and maximum portions in grams using `Min Portion (gm)` and `Max Portion (gm)` columns, respectively, if the ingredient is to be selected
-   Update `Type` as desired (see requirements below)

## Requirements Data

Specify requirements in `data/requirements.json`.

-   Pick an `objective` from the list: `["Calories", "Carbs", "Fat", "Total"]` to minimize the corresponding quantity in the recommended meal plan
-   Specify number of meal plans to recommend using `num_meals`
-   Specify minimum and maximum macronutrients requirements using the dictionaries `targets_min` and `targets_max`, respectively
-   Specify maximum number of ingredients to pick from a specific type using `type_limits`
-   Include or exclude any items by specifying the lists `include` or `exclude`, respectively
-   Provide inclusive and exclusive list of items by specifying the dictionaries `inclusive` and `exclusive`, respectively (see `data/requirements2.json` for an example)

## Optimization

Run `python src/mealplanner.py <nutrients.csv> <requirements.json> <output_path>`.

For e.g., `python src/mealplanner.py data/nutrients.csv data/requirements2.json out` gives the following optimal list of ingredients:

### Optimal Ingredients

```
Meal Plan 1:

Optimal Ingredients:
Isopure Protein Powder (gm): 50.0
2% Milk (gm): 100.0
Nonfat Greek Yogurt (gm): 150.0
Firm Tofu (gm): 200.0
Chickpea (gm): 150.0
Millet (gm): 200.0
Almonds (gm): 50.0
Pistachios (gm): 50.0
Oats (gm): 99.6

Macronutrients:
Total Calories (kcal): 2800.0
Carbs (gm): 344.0
Fat (gm): 82.9
Fiber (gm): 68.9
Protein (gm): 170.0

Meal Plan 2:
...
```

### Recipe Recommendations

Creates a list of recipes in files `out/meal_plan_N.txt` using OpenAI API if available. See `out.example/meal_plan_N.txt`.

# TODO

-   Replace `data/nutrients.csv` with complete USDA database
-   Move minimum and maximum portion size specifications to requirements
-   Move type specifications to requirements
-   Include a carbon footprint metric objective
-   Take existing inventory of ingredients and quantities and order ingredients as needed
-   Schedule meals over a given planning horizon (1-2 weeks)
