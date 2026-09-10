"""Pydantic schemas for daily production records.

`SHORTFALL_REASONS` / `VARIANCE_THRESHOLDS` are the single source of truth
for the shortfall-reason vocabulary and the on_target/slightly_below/
significantly_below cut points. The router imports these for validation and
also serves them via GET /production/shortfall-reasons and
GET /production/thresholds so the frontend reads them instead of
hardcoding a second copy (Field Intake Hardening §3.1/§3.3).
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.constants.validation_limits import MAX_TONNES

ShiftLiteral = Literal["day", "night", "general"]

ShortfallReasonLiteral = Literal[
    "equipment_failure",
    "maintenance",
    "weather",
    "material_availability",
    "labour_shortage",
    "geological_conditions",
    "safety_stoppage",
    "other",
]

# value -> label, in the same order the UI chips have always shown them.
SHORTFALL_REASONS: list[tuple[str, str]] = [
    ("equipment_failure", "Equipment failure"),
    ("maintenance", "Maintenance"),
    ("weather", "Weather"),
    ("material_availability", "Material availability"),
    ("labour_shortage", "Labour shortage"),
    ("geological_conditions", "Geological conditions"),
    ("safety_stoppage", "Safety stoppage"),
    ("other", "Other"),
]

# variance_pct = (actual - target) / target * 100. Matches the frontend's
# classifyVariance() exactly (ProductionTab.jsx) so client and server never
# disagree on the boundary.
ON_TARGET_MIN_PCT = -3.0
SLIGHTLY_BELOW_MIN_PCT = -12.0


def classify_variance(variance_pct: float | None) -> str | None:
    if variance_pct is None:
        return None
    if variance_pct >= ON_TARGET_MIN_PCT:
        return "on_target"
    if variance_pct >= SLIGHTLY_BELOW_MIN_PCT:
        return "slightly_below"
    return "significantly_below"


class ShortfallReasonOut(BaseModel):
    value: str
    label: str


class ProductionThresholdsOut(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "on_target_min_pct": -3.0,
                "slightly_below_min_pct": -12.0,
            }
        }
    )

    on_target_min_pct: float = ON_TARGET_MIN_PCT
    slightly_below_min_pct: float = SLIGHTLY_BELOW_MIN_PCT


class ProductionRecordOut(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 42,
                "site_id": 1,
                "date": "2026-08-29",
                "shift": "day",
                "actual_output": 712.4,
                "target_output": 1062.5,
                "variance_pct": -32.96,
                "variance_class": "significantly_below",
                "operating_hours": 11.5,
                "downtime_hours": 1.0,
                "material_processed": 730.0,
                "quality_grade": 31.2,
                "shortfall_reasons": ["equipment_failure"],
                "shortfall_other_note": None,
                "created_at": "2026-08-29T18:05:00Z",
                "updated_at": None,
                "created_by": "system",
                "updated_by": None,
            }
        },
    )

    id: int
    site_id: int
    date: date
    shift: str
    actual_output: float | None
    target_output: float | None
    variance_pct: float | None
    variance_class: str | None
    operating_hours: float | None
    downtime_hours: float | None
    material_processed: float | None
    quality_grade: float | None
    shortfall_reasons: list[str] | None
    shortfall_other_note: str | None
    created_at: datetime
    updated_at: datetime | None
    created_by: str | None
    updated_by: str | None


class ProductionRecordCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "site_id": 1,
                "date": "2026-08-31",
                "shift": "day",
                "actual_output": 1180.0,
                "target_output": 1250.0,
                "operating_hours": 22.0,
                "downtime_hours": 2.0,
                "material_processed": 1150.0,
                "quality_grade": 32.5,
                "shortfall_reasons": [],
                "shortfall_other_note": None,
            }
        }
    )

    site_id: int
    date: date
    shift: ShiftLiteral = "general"
    actual_output: float = Field(
        ge=0, le=MAX_TONNES, description="Tonnes actually produced; must be non-negative"
    )
    target_output: float = Field(
        gt=0, le=MAX_TONNES, description="Planned tonnes target; must be positive"
    )
    operating_hours: float | None = Field(None, ge=0, le=24)
    downtime_hours: float | None = Field(None, ge=0, le=24)
    material_processed: float | None = Field(None, ge=0, le=MAX_TONNES)
    quality_grade: float | None = Field(None, ge=0, le=100)
    shortfall_reasons: list[ShortfallReasonLiteral] = Field(default_factory=list)
    shortfall_other_note: str | None = None

    @model_validator(mode="after")
    def _check_hours_and_other_note(self) -> "ProductionRecordCreate":
        if (
            self.operating_hours is not None
            and self.downtime_hours is not None
            and self.operating_hours + self.downtime_hours > 24
        ):
            raise ValueError(
                "operating_hours + downtime_hours must not exceed 24 "
                f"(got {self.operating_hours} + {self.downtime_hours})"
            )
        if "other" in self.shortfall_reasons and not (
            self.shortfall_other_note and self.shortfall_other_note.strip()
        ):
            raise ValueError(
                "shortfall_other_note is required when shortfall_reasons includes 'other'"
            )
        return self


class ProductionRecordUpdate(BaseModel):
    """Partial update for PATCH /production/{id}. `site_id`/`date`/`shift`
    are the record's identity (and its uniqueness key) and are not editable
    here — create a new record instead if the shift itself was wrong.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "actual_output": 1195.0,
                "quality_grade": 33.0,
            }
        }
    )

    actual_output: float | None = Field(None, ge=0, le=MAX_TONNES)
    target_output: float | None = Field(None, gt=0, le=MAX_TONNES)
    operating_hours: float | None = Field(None, ge=0, le=24)
    downtime_hours: float | None = Field(None, ge=0, le=24)
    material_processed: float | None = Field(None, ge=0, le=MAX_TONNES)
    quality_grade: float | None = Field(None, ge=0, le=100)
    shortfall_reasons: list[ShortfallReasonLiteral] | None = None
    shortfall_other_note: str | None = None

    @field_validator("*", mode="before")
    @classmethod
    def _empty_string_is_none(cls, value):
        return None if value == "" else value
