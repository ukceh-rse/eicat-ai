from fastapi import APIRouter, Query
from typing import List
from pygbif import species
from eicat_ai.models import SpeciesNames

router = APIRouter(
    prefix="/gbif",
    tags=["GBIF"]
)


@router.get("/search", response_model=List[SpeciesNames])
async def search(q: str = Query(..., description="Search term for species name")) -> List[SpeciesNames]:
    """
    Search for species information from GBIF using the species name.
    
    Args:
        q: Search term for species name
    
    Returns:
        List[SpeciesNames]: A list of up to 10 species names and their vernacular names.
    """
    try:
        # Use pygbif name_lookup to search for species
        results = species.name_lookup(q=q, limit=10)
        print(results)
        species_list = []
        if 'results' in results:
            for result in results['results']:
                # Extract scientific name
                scientific_name = result.get('scientificName', result.get('canonicalName', ''))
                
                # Extract vernacular names if available
                vernacular_names = []
                if 'vernacularNames' in result:
                    vernacular_names = [vn.get('vernacularName', '') for vn in result['vernacularNames'] if vn.get('vernacularName')]
                
                if scientific_name:
                    species_list.append(SpeciesNames(
                        scientific_name=scientific_name,
                        vernacular_names=vernacular_names
                    ))
        
        return species_list[:10]  # Ensure we return max 10 results
        
    except Exception:
        # Return empty list if there's an error
        return []