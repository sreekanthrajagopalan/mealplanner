# Meal Planner

Given a database of ingredients with macronutrients information and daily requirements, the program recommends optimal ingredients to use for meal planning.

# Requirements

-   Python 3.10
-   Use `requirements.txt` to install required packages

# Usage

## Nutrients Data

Use `data/nutrients.csv` and update as needed.

-   Macronutrients information is from [USDA FoodData Central Search](https://fdc.nal.usda.gov/food-search)
-   Specify minimum and maximum portions in grams using `Min Portion (gm)` and `Max Portion (gm)` columns, respectively, if the ingredient is to be selected
-   Update `Type` as desired (see requirements below)

## Requirements Data

Specify requirements in `data/requirementsN.json`.

-   Pick an `objective` from the list: `["Calories", "Carbs", "Fat", "Total"]` to minimize the corresponding quantity in the recommended meal plan
-   Specify minimum and maximum macronutrients requirements using the dictionaries `targets_min` and `targets_max`, respectively
-   Specify maximum number of ingredients to pick from a specific type using `type_limits`
-   Include or exclude any items by specifying the lists `include` or `exclude`, respectively
-   Provide inclusive and exclusive list of items by specifying the dictionaries `inclusive` and `exclusive`, respectively (see `data/requirements2.json` for an example)

# TODO

-   Replace `data/nutrients.csv` with complete USDA database
-   Move minimum and maximum portion size specifications to requirements
-   Move type specifications to requirements
-   Find recipes to make with optimal ingredients and portions
-   Take existing inventory of ingredients and quantities and order ingredients as needed
-   Schedule meals over a given planning horizon (1-2 weeks)
