import pandas as pd
from pandas import DataFrame


def normalize_impact_string(s):
    if pd.isna(s) or not isinstance(s, str):
        return s
    return (
        s.strip()
        .lower()
        .replace("deseace", "disease")
        .replace("ecosystems", "ecosystem")
    )


if __name__ == "__main__":
    df: DataFrame = pd.read_excel("../GISD+EICAT+export.xlsx")
    df["Impact mechanism"] = df["Impact mechanism"].apply(normalize_impact_string)

    eicat_df: DataFrame = df.dropna(subset=["EICAT Category"])
    eicat_non_dd_df = eicat_df[eicat_df["EICAT Category"] != "DD"]
    number_of_references: int = eicat_df["Reference"].nunique()
    max_impact_df: DataFrame = eicat_df[eicat_df["Max Impact"] == "YES"]
    unique_species_df: int = len(max_impact_df.drop_duplicates(subset=["Species"]))

    print(f"References: {number_of_references}\nSpecies: {unique_species_df}")
    for col in ["EICAT Category", "Impact mechanism", "System", "Kingdom"]:
        print(eicat_non_dd_df[col].value_counts())
