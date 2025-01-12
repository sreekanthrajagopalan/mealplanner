import argparse
import json
import highspy
import openai
import os

import polars as pl

from dotenv import load_dotenv, find_dotenv
from typing import Tuple, Dict

# Load the environment variables from the .env file
api_key: str
if find_dotenv():
    load_dotenv()
    print("Loaded .env file")

    # Access the OpenAI API key
    api_key = os.getenv("OPENAI_API_KEY")

else:
    print(".env file not found")


def get_data(data_file: str, requirements_file: str) -> Tuple[pl.DataFrame, Dict]:
    """Get list of ingredients with macronutrients data and requirements from provided files

    Args:
        data_file (str): Path to nutrition data CSV file
        requirements_file (str): Path to requirements JSON file

    Returns:
        Tuple[pl.DataFrame, Dict]: DataFrame and Dictionary with required data for the model
    """

    # get data
    data = pl.scan_csv(data_file).collect()

    # get requirements
    with open(requirements_file, "r") as f:
        requirements = json.load(f)

    return (data, requirements)


def find_ingredients(data: pl.DataFrame, requirements: Dict) -> Dict:
    """Find optimal ingredients to meat nutrition requirements

    Args:
        data (pl.DataFrame): DataFrame with macronutrients data
        requirements (Dict): Dictionary with macronutrients requirements

    Returns:
        highspy.Highs: HiGHS MIP model
    """

    # objective: Calories, Carbs, Fat, Total (default)
    obj = requirements["objective"]

    # initialize math model
    h = highspy.Highs()

    # add vars
    x_qty = {
        row["Ingredient"]: h.addVariable(lb=0, ub=row["Max Portion (gm)"])
        for row in data.iter_rows(named=True)
    }
    y_pick = {row["Ingredient"]: h.addBinary() for row in data.iter_rows(named=True)}

    # add constraints

    ## ingredient limit if picked
    c_pick_lb = {
        row["Ingredient"]: h.addConstr(
            x_qty[row["Ingredient"]]
            >= row["Min Portion (gm)"] * y_pick[row["Ingredient"]]
        )
        for row in data.iter_rows(named=True)
    }
    c_pick_ub = {
        row["Ingredient"]: h.addConstr(
            x_qty[row["Ingredient"]]
            <= row["Max Portion (gm)"] * y_pick[row["Ingredient"]]
        )
        for row in data.iter_rows(named=True)
    }

    ## meet nutritional targets
    c_targets_min = {
        nut: h.addConstr(
            sum(
                row[nut] / row["Standard Portion (gm)"] * x_qty[row["Ingredient"]]
                for row in data.iter_rows(named=True)
            )
            >= tar
        )
        for nut, tar in requirements["targets_min"].items()
    }
    c_targets_max = {
        nut: h.addConstr(
            sum(
                row[nut] / row["Standard Portion (gm)"] * x_qty[row["Ingredient"]]
                for row in data.iter_rows(named=True)
            )
            <= tar
        )
        for nut, tar in requirements["targets_max"].items()
    }

    ## ingredient limit by type
    c_type_limits = {
        typ: h.addConstr(
            sum(
                y_pick[row["Ingredient"]]
                for row in data.filter(pl.col("Type") == typ).iter_rows(named=True)
            )
            <= lim
        )
        for typ, lim in requirements["type_limits"].items()
    }

    ## include ingredients
    c_include = {
        item: h.addConstr(
            sum(
                y_pick[row["Ingredient"]]
                for row in data.filter(
                    pl.col("Ingredient").str.contains(item)
                ).iter_rows(named=True)
            )
            == 1
        )
        for item in requirements["include"]
    }

    ## exclude ingredients
    c_exclude = {
        item: h.addConstr(
            sum(
                y_pick[row["Ingredient"]]
                for row in data.filter(
                    pl.col("Ingredient").str.contains(item)
                ).iter_rows(named=True)
            )
            == 0
        )
        for item in requirements["exclude"]
    }

    # inclusive ingredients
    for item, reqs in requirements["inclusive"].items():
        for type, grp in reqs.items():
            if type == "or":
                for row in data.filter(
                    pl.col("Ingredient").str.contains(item)
                ).iter_rows(named=True):
                    h.addConstr(
                        y_pick[row["Ingredient"]]
                        <= sum(
                            y_pick[row2["Ingredient"]]
                            for item2 in grp
                            for row2 in data.filter(
                                pl.col("Ingredient").str.contains(item2)
                            ).iter_rows(named=True)
                        )
                    )
            elif type == "and":
                for row in data.filter(
                    pl.col("Ingredient").str.contains(item)
                ).iter_rows(named=True):
                    for item2 in grp:
                        for row2 in data.filter(
                            pl.col("Ingredient").str.contains(item2)
                        ).iter_rows(named=True):
                            h.addConstr(
                                y_pick[row["Ingredient"]] <= y_pick[row2["Ingredient"]]
                            )

    # exclusive ingredients
    for item, reqs in requirements["exclusive"].items():
        for type, grp in reqs.items():
            if type == "or":
                for row in data.filter(
                    pl.col("Ingredient").str.contains(item)
                ).iter_rows(named=True):
                    h.addConstr(
                        1 - y_pick[row["Ingredient"]]
                        >= sum(
                            y_pick[row2["Ingredient"]]
                            for item2 in grp
                            for row2 in data.filter(
                                pl.col("Ingredient").str.contains(item2)
                            ).iter_rows(named=True)
                        )
                    )
            elif type == "and":
                for row in data.filter(
                    pl.col("Ingredient").str.contains(item)
                ).iter_rows(named=True):
                    for item2 in grp:
                        for row2 in data.filter(
                            pl.col("Ingredient").str.contains(item2)
                        ).iter_rows(named=True):
                            h.addConstr(
                                1 - y_pick[row["Ingredient"]]
                                >= y_pick[row2["Ingredient"]]
                            )

    # optimize

    ## min calories
    if obj == "Calories":
        h.minimize(
            sum(
                row["Total Calories (kcal)"]
                / row["Standard Portion (gm)"]
                * x_qty[row["Ingredient"]]
                for row in data.iter_rows(named=True)
            )
        )

    ## min carbs
    elif obj == "Carbs":
        h.minimize(
            sum(
                row["Carbs (gm)"]
                / row["Standard Portion (gm)"]
                * x_qty[row["Ingredient"]]
                for row in data.iter_rows(named=True)
            )
        )

    ## min fat
    elif obj == "Fat":
        h.minimize(
            sum(
                row["Fat (gm)"]
                / row["Standard Portion (gm)"]
                * x_qty[row["Ingredient"]]
                for row in data.iter_rows(named=True)
            )
        )

    ## min total quantity
    else:
        h.minimize(sum(x_qty[row["Ingredient"]] for row in data.iter_rows(named=True)))

    solutions = dict()
    c_cut = dict()
    for opt in range(requirements["num_meals"]):
        # optimize
        h.run()

        # get solution
        solution = h.getSolution()
        info = h.getInfo()
        model_status = h.getModelStatus()

        if model_status == highspy.HighsModelStatus.kOptimal:
            solutions[opt + 1] = {
                "optimal_ingredients": {
                    f"{row['Ingredient']} (gm)": round(
                        solution.col_value[x_qty[row["Ingredient"]].index], ndigits=1
                    )
                    for row in data.iter_rows(named=True)
                    if solution.col_value[y_pick[row["Ingredient"]].index] > 0.99
                },
                "macronutrients": {
                    nut: round(solution.row_value[c_targets_min[nut].index], ndigits=1)
                    for nut in requirements["targets_min"].keys()
                },
            }

        # add integer cut
        c_cut[opt] = h.addConstr(
            sum(
                (
                    y_pick[row["Ingredient"]]
                    if solution.col_value[y_pick[row["Ingredient"]].index] < 0.01
                    else (1 - y_pick[row["Ingredient"]])
                )
                for row in data.iter_rows(named=True)
            )
            >= 1
        )

    return solutions


def plan_meal(data: pl.DataFrame, requirements: Dict, output_path: str) -> None:
    """Find optimal meal plan

    Args:
        data (pl.DataFrame): DataFrame with macronutrients data
        requirements (Dict): Dictionary with macronutrients requirements
        output_path (str): Path to save meal plans
    """

    solutions = find_ingredients(data=data, requirements=requirements)

    # get meal plan using LLM
    try:
        client = openai.OpenAI(api_key=api_key)
        for opt, sol in solutions.items():

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"Find recipes for a drink, breakfast, lunch, afternoon snack, and dinner with following ingredients exactly meeting the total weight amount of each ingredient over all the recipes: {sol['optimal_ingredients']} ",
                            }
                        ],
                    }
                ],
                response_format={"type": "text"},
                temperature=1,
                max_completion_tokens=2048,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0,
            )

            try:
                if not os.path.exists(output_path):
                    os.makedirs(output_path)

                with open(os.path.join(output_path, f"meal_plan_{opt}.txt"), "w") as f:
                    f.write(response.choices[0].message.content)
                print(f"\nCreated meal plan {opt} in {output_path}/meal_plan{opt}.txt")

            except:
                print(f"\nMeal Plan {opt}")
                print(response.choices[0].message.content)

    except:
        print(
            "Unable to get meal plan from OpenAI. See optimal list of ingredients below."
        )
        for opt, sol in solutions.items():
            print(f"\nMeal Plan {opt}:")

            print(f"\nOptimal Ingredients:")
            for item, val in sol["optimal_ingredients"].items():
                print(f"{item}: {val}")

            print(f"\nMacronutrients:")
            for nut, val in sol["macronutrients"].items():
                print(f"{nut}: {val}")


if __name__ == "__main__":
    # parse arguments
    parser = argparse.ArgumentParser(
        prog="Meal Planner",
        description="Find ingredients to meet target macronutrient requirements",
    )
    parser.add_argument("data_file", type=str)
    parser.add_argument("requirements_file", type=str)
    parser.add_argument("output_path", type=str)
    args = parser.parse_args()

    # get data
    data, requirements = get_data(
        data_file=args.data_file, requirements_file=args.requirements_file
    )

    # get meal plan
    plan_meal(data=data, requirements=requirements, output_path=args.output_path)
