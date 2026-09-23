"""Size-profile endpoints (F5.20) — the fashion measurements side of the profile.

`GET/PATCH /auth/me/size-profile`: account-scoped, `CurrentUser`-guarded, and
always scoped to the caller — the path carries no user id, so cross-user access
is not expressible (R9). `PATCH` follows the repo's clear convention: omitted =
unchanged, explicit `null` = cleared. The row is created on the first PATCH
(one-to-one, `user_id` is the primary key), so a customer who never opens
«سایز من» has no row at all. Ranges are enforced by the schema (422) and
mirrored by the database CHECKs; the units are centimetres / kilograms and are
documented on the schema and in the UI labels.
"""

from fastapi import APIRouter
from sqlalchemy import text

from app.auth import CurrentUser, DbSession
from app.schemas import SizeProfileOut, SizeProfileUpdateIn

router = APIRouter(prefix="/auth/me", tags=["auth"])


def _to_out(row) -> SizeProfileOut:
    return SizeProfileOut(
        height_cm=row["height_cm"],
        weight_kg=row["weight_kg"],
        chest_cm=row["chest_cm"],
        waist_cm=row["waist_cm"],
        hip_cm=row["hip_cm"],
        preferred_top_size=row["preferred_top_size"],
        preferred_bottom_size=row["preferred_bottom_size"],
        preferred_shoe_size=row["preferred_shoe_size"],
        fit_preference=row["fit_preference"],
        updated_at=row["updated_at"].isoformat() if row["updated_at"] else None,
    )


async def _load_row(session, user_id):
    return (
        await session.execute(
            text("SELECT * FROM public.user_size_profiles WHERE user_id = :uid"),
            {"uid": str(user_id)},
        )
    ).mappings().first()


@router.get("/size-profile", response_model=SizeProfileOut)
async def get_size_profile(user: CurrentUser, session: DbSession) -> SizeProfileOut:
    """The caller's measurements; all nulls when nothing was saved yet."""
    row = await _load_row(session, user.id)
    if row is None:
        return SizeProfileOut()
    return _to_out(row)


@router.patch("/size-profile", response_model=SizeProfileOut)
async def update_size_profile(
    body: SizeProfileUpdateIn, user: CurrentUser, session: DbSession
) -> SizeProfileOut:
    """Upsert the caller's measurements (omitted = unchanged, null = cleared)."""
    columns = (
        "height_cm", "weight_kg", "chest_cm", "waist_cm", "hip_cm",
        "preferred_top_size", "preferred_bottom_size", "preferred_shoe_size",
        "fit_preference",
    )
    sets: list[str] = []
    params: dict = {"uid": str(user.id)}
    sent = body.model_fields_set  # distinguishes omitted (unchanged) from null (cleared)
    for column in columns:
        if column in sent:
            sets.append(f"{column} = :{column}")
            params[column] = getattr(body, column)

    if sets:
        # updated_at moves on every accepted write; created_at only on insert
        await session.execute(
            text(
                "INSERT INTO public.user_size_profiles (user_id) "
                "VALUES (:uid) ON CONFLICT (user_id) DO NOTHING"
            ),
            params,
        )
        await session.execute(
            text(
                f"UPDATE public.user_size_profiles SET {', '.join(sets)}, "
                "updated_at = now() WHERE user_id = :uid"
            ),
            params,
        )
        await session.commit()

    row = await _load_row(session, user.id)
    if row is None:
        return SizeProfileOut()
    return _to_out(row)
