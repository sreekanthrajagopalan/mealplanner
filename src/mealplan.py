import highspy
import polars as pl


def main():

    # get data
    data = pl.scan_csv("data/nutrients.csv").collect()

    # constraints
    targets_min = {
        "Total Calories (kcal)": 3000,
        "Carbs (gm)": 200,
        "Fat (gm)": 80,
        "Fiber (gm)": 40,
        "Protein (gm)": 160,
    }
    targets_max = {
        "Total Calories (kcal)": 3200,
        "Carbs (gm)": 400,
        "Fat (gm)": 90,
        "Fiber (gm)": 70,
        "Protein (gm)": 175,
    }
    limits_num = {"Essential": 3, "Meal": 4, "Snack": 3}
    milk = 100
    pick_tofu = 1

    # initialize math model
    h = highspy.Highs()

    # add vars
    x_qty = {
        row["Ingredient"]: h.addVariable(lb=0, ub=row["Limit (gm)"])
        for row in data.iter_rows(named=True)
    }
    y_pick = {row["Ingredient"]: h.addBinary() for row in data.iter_rows(named=True)}

    # add constraints

    ## add milk
    c_milk = h.addConstr(
        sum(
            x_qty[row["Ingredient"]]
            for row in data.filter(pl.col("Ingredient").str.contains("Milk")).iter_rows(
                named=True
            )
        )
        == milk
    )

    ## pick tofu
    c_pick_tofu = h.addConstr(
        sum(
            y_pick[row["Ingredient"]]
            for row in data.filter(pl.col("Ingredient").str.contains("Tofu")).iter_rows(
                named=True
            )
        )
        == pick_tofu
    )

    ## ingredient limit if picked
    c_pick = {
        row["Ingredient"]: h.addConstr(
            x_qty[row["Ingredient"]] <= row["Limit (gm)"] * y_pick[row["Ingredient"]]
        )
        for row in data.iter_rows(named=True)
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
        for typ, lim in limits_num.items()
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
        for nut, tar in targets_min.items()
    }
    c_targets_max = {
        nut: h.addConstr(
            sum(
                row[nut] / row["Standard Portion (gm)"] * x_qty[row["Ingredient"]]
                for row in data.iter_rows(named=True)
            )
            <= tar
        )
        for nut, tar in targets_max.items()
    }

    # optimize
    # h.minimize(sum(x_qty[row["Ingredient"]] for row in data.iter_rows(named=True)))
    h.minimize(
        sum(
            row["Carbs (gm)"] / row["Standard Portion (gm)"] * x_qty[row["Ingredient"]]
            for row in data.iter_rows(named=True)
        )
    )
    h.run()

    solution = h.getSolution()
    info = h.getInfo()
    model_status = h.getModelStatus()
    print("Model status = ", h.modelStatusToString(model_status))
    print("Optimal objective = ", info.objective_function_value)
    print("Solution: ")
    for row in data.iter_rows(named=True):
        if solution.col_value[y_pick[row["Ingredient"]].index] > 0.99:
            print(
                f"{row['Ingredient']}: {solution.col_value[x_qty[row['Ingredient']].index]:.1f}"
            )
    print("Macronutrients: ")
    for nut in targets_min.keys():
        print(f"{nut}: {solution.row_value[c_targets_min[nut].index]:.1f}")
    print("Exit")


if __name__ == "__main__":
    main()
