import argparse
import json
import highspy
import polars as pl


def find_ingredients(data_file: str, requirements_file: str) -> None:
    """Find optimal ingredients by solving a MIP.

    Args:
        data_file (str): Path to nutrition data CSV file
        requirements_file (str): Path to requirements JSON file
    """

    # get data
    data = pl.scan_csv(data_file).collect()

    # get requirements
    with open(requirements_file, "r") as f:
        requirements = json.load(f)

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

    h.run()

    solution = h.getSolution()
    info = h.getInfo()
    model_status = h.getModelStatus()

    print(f"\nModel Status = {h.modelStatusToString(model_status)}")

    print(f"\nOptimal Objective = {info.objective_function_value:.1f}")

    print("\nOptimal Ingredients:")
    for row in data.iter_rows(named=True):
        if solution.col_value[y_pick[row["Ingredient"]].index] > 0.99:
            print(
                f"{row['Ingredient']} (gm): {solution.col_value[x_qty[row['Ingredient']].index]:.1f}"
            )
    print("Add fruits and vegetables!")

    print("\nMacronutrients:")
    for nut in requirements["targets_min"].keys():
        print(f"{nut}: {solution.row_value[c_targets_min[nut].index]:.1f}")


if __name__ == "__main__":
    # parse arguments
    parser = argparse.ArgumentParser(
        prog="Meal Planner",
        description="Find ingredients to meet target macronutrient requirements",
    )
    parser.add_argument("data_file", type=str)
    parser.add_argument("requirements_file", type=str)
    args = parser.parse_args()

    # find optimal ingredients
    find_ingredients(data_file=args.data_file, requirements_file=args.requirements_file)
