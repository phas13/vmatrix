from pydantic import BaseModel


class CompetencyAreaStat(BaseModel):
    category_name: str
    avg_score: int  # integer 0-100


class HRStatsResponse(BaseModel):
    level_distribution: dict[str, int]      # e.g. {"junior": 3, "middle": 5, "senior": 2}
    avg_progress_per_level: dict[str, int]  # e.g. {"junior": 42, "middle": 67, "senior": 85}
    strongest_areas: list[CompetencyAreaStat]
    weakest_areas: list[CompetencyAreaStat]
