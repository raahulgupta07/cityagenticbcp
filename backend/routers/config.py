"""Config router — sectors, thresholds, settings."""
from fastapi import APIRouter
from config.settings import (
    SECTORS, HEATMAP_THRESHOLDS, HEATMAP_COLORS, ALERTS,
    BCP_WEIGHTS, BCP_GRADES, ENERGY_COST, ENERGY_DECISION, VALIDATION,
)

router = APIRouter()


@router.get("/config")
def get_config():
    return {
        "sectors": SECTORS,
        "heatmap_thresholds": HEATMAP_THRESHOLDS,
        "heatmap_colors": HEATMAP_COLORS,
        "alerts": ALERTS,
        "bcp_weights": BCP_WEIGHTS,
        "bcp_grades": BCP_GRADES,
        "energy_cost": ENERGY_COST,
        "energy_decision": ENERGY_DECISION,
        "validation": VALIDATION,
    }


@router.get("/config/sectors")
def get_sectors():
    return SECTORS
