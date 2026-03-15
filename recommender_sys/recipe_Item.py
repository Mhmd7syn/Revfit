from dataclasses import dataclass
from typing import List, Optional


@dataclass
class RecipeItem:
    # ---- Identity ----
    recipe_id: str
    title: str

    # ---- Classification ----
    cuisine: str                    # e.g. "middle eastern", "italian"
    diet_labels: List[str]          # e.g. ["vegetarian", "vegan"]
    intolerances: List[str]         # e.g. ["gluten", "dairy"]

    # ---- Nutrition (per serving) ----
    calories: float                 # kcal
    protein_g: float
    carbs_g: float
    fat_g: float

    # ---- Cooking info ----
    prep_time_min: int

    # ---- Optional ----
    rating: Optional[float] = None  # 0.0 – 5.0
    image_url: Optional[str] = None
    source_url: Optional[str] = None

    def __post_init__(self):
        # Normalise cuisine to lowercase for reliable matching
        self.cuisine = self.cuisine.lower().strip()
        self.diet_labels = [d.lower().strip() for d in self.diet_labels]
        self.intolerances = [i.lower().strip() for i in self.intolerances]
