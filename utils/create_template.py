from openpyxl import Workbook
from openpyxl.styles import Alignment
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation


def create_data_validation(col_letter, col_def):
    values = col_def.get("values")
    name = col_def["name"]
    quoted = ", ".join(f'"{v}"' for v in values)
    dv = DataValidation(
        type="list",
        formula1=f'"{",".join(values)}"',
        allow_blank=True,
        showDropDown=False,
        showErrorMessage=True,
        errorTitle="Invalid value",
        error=f"Column {name} only accepts {quoted}.",
        showInputMessage=True,
    )
    dv.sqref = f"{col_letter}2:{col_letter}{100}"
    return dv


def create_template(
    columns: list[dict], output_path: str = "template.xlsx", max_col_width: int = 30
):
    wb = Workbook()
    ws = wb.active
    ws.title = "Data"

    for col_idx, col_def in enumerate(columns, start=1):
        ws.cell(row=1, column=col_idx, value=col_def["name"])
        col_letter = get_column_letter(col_idx)

        if col_def.get("values"):
            dv = create_data_validation(col_letter, col_def)
            ws.add_data_validation(dv)

        candidates = [col_def["name"]] + (col_def.get("values") or [])
        max_width = col_def.get("width") or min(
            max(len(s) for s in candidates), max_col_width
        )
        ws.column_dimensions[col_letter].width = max_width
        for row in range(2, 101):
            ws.cell(row=row, column=col_idx).alignment = Alignment(wrap_text=True)

    wb.save(output_path)
    print(f"Template saved to: {output_path}")


if __name__ == "__main__":
    create_template(
        columns=[
            {
                "name": "Species/Reference Text",
                "values": [
                    "Common coquí (Eleutherodactylus coqui) / Smith et al. (2017)",
                    "Red-breasted parakeet (Psittacula alexandri) / Neo et al. (2012)",
                    "House crow (Corvus splendens) / Roll et al. (2007)",
                    "Japanese quail (Coturnix japonica) / Barilani et al. (2005)",
                    "Common myna (Acridotheres tristis) / Hughes et al. (2017)",
                    "Asian common toad (Duttaphrynus melanostictus) / Church et al. (1960)",
                ],
            },
            {
                "name": "EICAT Category",
                "values": [
                    "Massive",
                    "Major",
                    "Moderate",
                    "Minor",
                    "Minimal Concern",
                    "Data Deficient",
                    "No Alien Populations",
                ],
            },
            {
                "name": "Impact mechanism",
                "values": [
                    "Competition",
                    "Predation",
                    "Hybridisation",
                    "Transmission of disease",
                    "Parasitism",
                    "Poisoning/toxicity",
                    "Bio-fouling or other direct physical disturbance",
                    "Grazing/herbivory/browsing",
                    "Chemical impact on ecosystem",
                    "Physical impact on ecosystem",
                    "Structural impact on ecosystem",
                    "Indirect impacts through interactions with other species",
                ],
            },
            {"name": "Evidence for EICAT impact category", "width": 60},
            {"name": "Confidence Rating", "values": ["low", "medium", "high"]},
            {"name": "Impacted native species"},
        ]
    )
