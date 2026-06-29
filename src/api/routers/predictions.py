import csv
import io
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import asc, desc, func, select

from src.api.core.dependencies import CurrentUser, DBDep
from src.api.core.openapi import HTTP_401, HTTP_403, HTTP_404, HTTP_422
from src.api.core.permissions import is_admin
from src.api.models.prediction import Prediction
from src.api.schemas.common import Page
from src.api.schemas.prediction import PredictionBatchRequest, PredictionCreateRequest, PredictionResponse

router = APIRouter(prefix="/predictions", tags=["Predictions"])

_PRED_SORT_FIELDS: dict[str, Any] = {
    "created_at": Prediction.created_at,
    "site_id": Prediction.site_id,
    "horizon_days": Prediction.horizon_days,
    "model_type": Prediction.model_type,
}


def _stub_predict(req: PredictionCreateRequest) -> dict:
    """Placeholder until ML inference is implemented."""
    return {
        "status": "stub",
        "note": "ML inference not yet implemented.",
        "bloom_probability": None,
        "risk_continuous": None,
        "trophic_state": None,
        "trophic_memberships": None,
        "irc": None,
        "state_vector": None,
        "uncertainty": {"risk_lower": None, "risk_upper": None, "picp_nominal": 0.90},
        "model_version": "0.1.0-stub",
    }


@router.post(
    "",
    response_model=PredictionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run a prediction",
    description=(
        "Execute a **synchronous** single-point inference and store the result. "
        "Returns `201 Created` with the result inline — no polling required.\n\n"
        "> **Note:** ML inference is currently a stub. Output fields such as "
        "`bloom_probability` will be `null` until model implementations are connected.\n\n"
        "**Input variables** (all optional individually):\n\n"
        "| Variable | Unit | Role |\n"
        "|---|---|---|\n"
        "| `TP_ugL` | µg/L | Total phosphorus — primary eutrophication driver |\n"
        "| `TN_ugL` | µg/L | Total nitrogen — co-limiting nutrient |\n"
        "| `chlorophyll_a_ugL` | µg/L | Algal biomass proxy |\n"
        "| `DO_mgL` | mg/L | Dissolved oxygen |\n"
        "| `pH` | — | Dimensionless |\n"
        "| `turbidity_NTU` | NTU | Light availability |\n"
        "| `temperature_C` | °C | Thermal favorability for algal growth |\n"
        "| `secchi_depth_m` | m | Water transparency (auxiliary) |\n"
        "| `wind_speed_ms` | m/s | Mixing/stratification (auxiliary) |\n"
        "| `residence_time_d` | days | Hydraulic retention time (auxiliary) |\n\n"
        "**Valid `horizon_days` values:** `30`, `60`, `90`."
    ),
    responses={
        422: {"description": "`year_month` not in YYYY-MM format, or `horizon_days` not in {30, 60, 90}."},
        **HTTP_401,
    },
)
async def create_prediction(body: PredictionCreateRequest, current_user: CurrentUser, db: DBDep):
    result = _stub_predict(body)
    prediction = Prediction(
        user_id=current_user.id,
        experiment_id=body.experiment_id,
        model_type=body.model,
        site_id=body.site_id,
        year_month=body.year_month,
        horizon_days=body.horizon_days,
        input_variables=body.variables.model_dump(exclude_none=True),
        result=result,
    )
    db.add(prediction)
    await db.commit()
    await db.refresh(prediction)
    return prediction


@router.post(
    "/batch",
    response_model=list[PredictionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Run predictions in batch",
    description=(
        "Execute up to **20 predictions** in a single request. "
        "Each item is validated and processed independently; "
        "all results are returned in the same order as the input list.\n\n"
        "Equivalent to calling `POST /predictions` once per item, "
        "but with reduced HTTP overhead for scripted evaluation workflows."
    ),
    responses={
        422: {"description": "Validation error in one or more prediction items."},
        **HTTP_401,
    },
)
async def create_predictions_batch(
    body: PredictionBatchRequest, current_user: CurrentUser, db: DBDep
):
    created = []
    for req in body.predictions:
        result = _stub_predict(req)
        prediction = Prediction(
            user_id=current_user.id,
            experiment_id=req.experiment_id,
            model_type=req.model,
            site_id=req.site_id,
            year_month=req.year_month,
            horizon_days=req.horizon_days,
            input_variables=req.variables.model_dump(exclude_none=True),
            result=result,
        )
        db.add(prediction)
        created.append(prediction)
    await db.flush()
    await db.commit()
    for p in created:
        await db.refresh(p)
    return created


@router.get(
    "",
    response_model=Page[PredictionResponse],
    summary="List predictions",
    description=(
        "Paginated list of predictions, ordered by `created_at` descending.\n\n"
        "- Regular users see only their own predictions.\n"
        "- Admins see all predictions.\n\n"
        "**Filters:** `?site_id=`, `?model=`, `?horizon_days=`."
    ),
    responses={**HTTP_401},
)
async def list_predictions(
    current_user: CurrentUser,
    db: DBDep,
    limit: int = Query(50, ge=1, le=200, description="Items per page"),
    offset: int = Query(0, ge=0, description="Zero-based page offset"),
    site_id: str | None = Query(None, description="Filter by exact site ID"),
    model: str | None = Query(None, description="Filter by model type"),
    horizon_days: int | None = Query(None, description="Filter by horizon (30, 60, or 90)"),
    sort_by: str = Query("created_at", description="Sort field: created_at | site_id | horizon_days | model_type"),
    order: str = Query("desc", description="Sort order: asc | desc"),
):
    base = select(Prediction)
    count_base = select(func.count()).select_from(Prediction)

    if not is_admin(current_user.system_role):
        base = base.where(Prediction.user_id == current_user.id)
        count_base = count_base.where(Prediction.user_id == current_user.id)
    if site_id:
        base = base.where(Prediction.site_id == site_id)
        count_base = count_base.where(Prediction.site_id == site_id)
    if model:
        base = base.where(Prediction.model_type == model)
        count_base = count_base.where(Prediction.model_type == model)
    if horizon_days:
        base = base.where(Prediction.horizon_days == horizon_days)
        count_base = count_base.where(Prediction.horizon_days == horizon_days)

    if sort_by not in _PRED_SORT_FIELDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid sort_by '{sort_by}'. Valid values: {sorted(_PRED_SORT_FIELDS)}",
        )
    col = _PRED_SORT_FIELDS[sort_by]
    order_clause = desc(col) if order.lower() != "asc" else asc(col)

    total = (await db.execute(count_base)).scalar_one()
    items = list(
        (await db.execute(base.order_by(order_clause).limit(limit).offset(offset)))
        .scalars()
        .all()
    )
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/{prediction_id}/download",
    response_model=None,
    summary="Download prediction as CSV",
    description=(
        "Download the prediction inputs and result as a **single-row CSV** file, "
        "suitable for import into spreadsheets or notebooks.\n\n"
        "**Columns:** `prediction_id`, `site_id`, `year_month`, `horizon_days`, `model_type`, "
        "`input_<variable>` (one column per provided input variable), `bloom_probability`, "
        "`risk_continuous`, `trophic_state`, `irc`, `uncertainty_lower`, `uncertainty_upper`, "
        "`created_at`."
    ),
    responses={
        200: {"content": {"text/csv": {}}, "description": "CSV file attachment."},
        **HTTP_401,
        **HTTP_403,
        **HTTP_404,
    },
)
async def download_prediction_csv(prediction_id: uuid.UUID, current_user: CurrentUser, db: DBDep):
    prediction = await db.get(Prediction, prediction_id)
    if not prediction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prediction not found")
    if not is_admin(current_user.system_role) and prediction.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    result = prediction.result or {}
    row = {
        "prediction_id": prediction.id,
        "site_id": prediction.site_id,
        "year_month": prediction.year_month,
        "horizon_days": prediction.horizon_days,
        "model_type": prediction.model_type,
        **{f"input_{k}": v for k, v in (prediction.input_variables or {}).items()},
        "bloom_probability": result.get("bloom_probability"),
        "risk_continuous": result.get("risk_continuous"),
        "trophic_state": result.get("trophic_state"),
        "irc": result.get("irc"),
        "uncertainty_lower": (result.get("uncertainty") or {}).get("risk_lower"),
        "uncertainty_upper": (result.get("uncertainty") or {}).get("risk_upper"),
        "created_at": prediction.created_at.isoformat(),
    }

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(row.keys()))
    writer.writeheader()
    writer.writerow(row)
    buf.seek(0)

    filename = f"prediction_{prediction.id}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/{prediction_id}",
    response_model=PredictionResponse,
    summary="Get prediction",
    description="Retrieve a single prediction and its result. Only the owner or an admin can access.",
    responses={**HTTP_401, **HTTP_403, **HTTP_404},
)
async def get_prediction(prediction_id: uuid.UUID, current_user: CurrentUser, db: DBDep):
    prediction = await db.get(Prediction, prediction_id)
    if not prediction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prediction not found")
    if not is_admin(current_user.system_role) and prediction.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return prediction
