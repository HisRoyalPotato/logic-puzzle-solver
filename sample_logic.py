houses = {"color": {1: "red", 2: "green", 3: "blue"}, "pet": {1: "cat", 2: "dog", 3: "bird"}}


# The 3 rules below:
# The red house is directly left of the green house.
# The cat lives in house 1.
# The bird is not in the blue house.

def violates(houses):
    for index in houses["color"]:
        if houses["color"][index] == "green":
            green_index = index
        if houses["color"][index] == "red":
            red_index = index
        if houses["color"][index] == "blue":
            blue_index = index

    if red_index != green_index - 1:
        return True

    if houses["pet"][1] != "cat":
        return True

    if houses["pet"][blue_index] != "bird":
        return True

    return False



