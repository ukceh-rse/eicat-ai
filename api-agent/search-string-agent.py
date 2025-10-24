from pydantic_ai import Agent, ModelSettings
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pygbif import species
from typing import List
import uvicorn


class SpeciesNames(BaseModel):
    scientific_name: str
    vernacular_names: List[str]


class SearchString(BaseModel):
    search_string: str
    species_names: SpeciesNames


agent: Agent[None, SearchString] = Agent(
    "bedrock:amazon.nova-lite-v1:0",
    output_type=SearchString,
    output_retries=2,
    model_settings=ModelSettings(max_tokens=10_000, temperature=0.0),
    system_prompt=(
        "You are a helpful assistant as part of a scientific support system. "
        "Your task is to return a search string to be used for an academic literature search. "
        "You should lookup the species scientific and vernacular names and select the most likely result based on the user input. "
        "Select the most likely species from the list returned. "
        "The academic search string should be created using all known scientific and vernacular names of the single specific species selected. "
        "Return only the search string, no pre-amble or explanation is required. "
        "The species will be provided by the user."
    ),
)


@agent.tool_plain
def create_search_string(species_names: SpeciesNames) -> SearchString:
    """Create a search string based on a list of common and scientific names of a certain species."""
    species_term: str = " OR ".join(
        [
            f'"{name}"'
            for name in [species_names.scientific_name] + species_names.vernacular_names
        ]
    )
    return SearchString(
        search_string=(
            '("introduced species" OR "invasive species" '
            'OR "invasive alien species" OR "IAS" OR "alien" OR "non-native" OR "nonindigenous" '
            'OR "pest" OR "feral" OR "exotic") AND ({species_term})'
        ).format(species_term=species_term),
        species_names=species_names,
    )


@agent.tool_plain
def lookup_species_names(species_name: str) -> List[SpeciesNames]:
    """Lookup scientific and vernacular names of a species in the GBIF (Global Biodiversity Information ) species database."""

    def extract_species_names(result) -> SpeciesNames:
        return SpeciesNames(
            scientific_name=result["scientificName"],
            vernacular_names=[
                v_name["vernacularName"] for v_name in result["vernacularNames"]
            ],
        )

    response = species.name_lookup(q=species_name, limit=10)
    return [extract_species_names(result) for result in response["results"]]


app = agent.to_ag_ui(debug=True)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or list of allowed origins like ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    print(f"App type: {type(app)}")
    uvicorn.run(app, host="127.0.0.1", port=8000)
