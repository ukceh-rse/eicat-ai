import urllib.parse

import pandas as pd
import plotly
import plotly.graph_objects as go
from pandas import DataFrame

category_mapping: dict = {
    "MV": "Massive",
    "MR": "Major",
    "MO": "Moderate",
    "MN": "Minor",
    "MC": "Minimal",
}

def normalize_impact_string(s):
    if pd.isna(s) or not isinstance(s, str):
        return s
    return (
        s.strip()
        .lower()
        .replace("deseace", "disease")
        .replace("desease", "disease")
        .replace("s to native species", "")
        .replace("ecosystems", "ecosystem")
        .replace("/ ", "/")
    )


def create_scholar_link(s):
    if pd.isna(s) or not isinstance(s, str):
        return s
    encoded_query = urllib.parse.quote_plus(s)
    return f'=HYPERLINK("https://scholar.google.com/scholar?q={encoded_query}"; "{s}")'


def create_sankey(df: pd.DataFrame, title: str = "Sankey Diagram") -> go.Figure:
    df = df[["System", "EICAT Category", "Impact mechanism"]]

    df["EICAT Category"] = df["EICAT Category"].replace(category_mapping)
    df.insert(0, "__total__", "Impacts")
    cols = df.columns.tolist()

    all_labels = pd.unique(df.values.ravel("K")).tolist()
    label_to_idx = {label: i for i, label in enumerate(all_labels)}

    flows = pd.concat(
        [
            df.groupby([source_col, target_col])
            .size()
            .reset_index(name="count")
            .rename(columns={source_col: "source", target_col: "target"})
            for source_col, target_col in zip(cols[:-1], cols[1:])
        ]
    )
    node_totals = flows.groupby("source")["count"].sum().to_dict()
    node_totals.update(flows.groupby("target")["count"].sum().to_dict())

    def fmt_label(l):
        label = l[:25] + "..." if len(l) > 25 else l
        return f"{label} ({node_totals.get(l, '')})"

    labeled = [fmt_label(l) for l in all_labels]

    palette = plotly.colors.qualitative.D3
    node_colors = [palette[i % len(palette)] for i, _ in enumerate(all_labels)]
    node_color_map = dict(zip(all_labels, node_colors))

    def to_rgba(color, alpha=0.3):
        if color.startswith("#"):
            r, g, b = plotly.colors.hex_to_rgb(color)
        else:
            r, g, b = plotly.colors.unlabel_rgb(color)
        return f"rgba({r},{g},{b},{alpha})"

    link_colors = [to_rgba(node_color_map[s]) for s in flows["source"]]

    fig = go.Figure(
        data=[
            go.Sankey(
                node=dict(
                    pad=15,
                    thickness=20,
                    line=dict(color="black", width=0.5),
                    label=labeled,
                    color=node_colors,
                ),
                link=dict(
                    source=flows.iloc[:, 0].map(label_to_idx).tolist(),
                    target=flows.iloc[:, 1].map(label_to_idx).tolist(),
                    value=flows["count"].tolist(),
                    color=link_colors,
                ),
            )
        ]
    )

    fig.update_layout(
        title_text=title,
        font_size=12,
        height=800,
        width=1200,
    )
    return fig


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
        print(eicat_non_dd_df[col].value_counts().to_markdown())

    sample: DataFrame = (
        eicat_non_dd_df.groupby(["EICAT Category", "Impact mechanism", "System"])
        .apply(lambda x: x.sample(frac=0.3, random_state=42))
        .reset_index()
    )

    sample = sample[["EICAT Category", "Impact mechanism", "Species", "System", "Reference"]]
    sample["Reference"] = sample["Reference"].apply(create_scholar_link)
    sample["EICAT Category"] = sample["EICAT Category"].replace(category_mapping)

    sample.to_csv("eicat_startified_sample.csv", index=False)

    fig: go.Figure = create_sankey(
        eicat_non_dd_df,
        title="GISD EICAT Distribution Flows",
    )
    fig.write_image("sankey.png")
    fig.write_html("sankey.html")
