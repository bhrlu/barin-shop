"""Own auth endpoints: signup, signin, current-user profile, password reset.

The store's own auth (it replaced Supabase Auth). Passwords are bcrypt-hashed;
sessions are HS256 JWTs issued by this service. On signup the profile row and the
default 'customer' role are created in the same transaction.
"""

import logging
import re

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.auth import CurrentUser, DbSession
from app.schemas import (
    ForgotPasswordRequest,
    ProfileUpdateIn,
    ResetPasswordRequest,
    SignInRequest,
    SignUpRequest,
    TokenOut,
    UserInfoOut,
)
from app.security import create_access_token, hash_password, verify_password
from app.services.password_reset import ResetError, request_reset, reset_password
from app.services.profile import normalize_birth_date, normalize_national_id
from app.services.roles import resolve_role

log = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


_PROFILE_COLUMNS = (
    "p.id, u.email, p.full_name, p.phone, p.avatar_url, p.created_at, "
    "p.first_name, p.last_name, p.birth_date, p.gender, p.national_id, "
    "p.email_verified_at, p.phone_verified_at"
)


async def _load_user(session, user_id) -> dict | None:
    row = (
        await session.execute(
            text(
                f"SELECT {_PROFILE_COLUMNS} "
                "FROM public.profiles p JOIN public.users u ON u.id = p.id WHERE p.id = :uid"
            ),
            {"uid": str(user_id)},
        )
    ).mappings().first()
    return dict(row) if row else None


def _iso(value) -> str | None:
    return value.isoformat() if value else None


async def _issue_token(session, user_id, email: str) -> TokenOut:
    role = await resolve_role(session, user_id)
    info = await _load_user(session, user_id) or {}
    return TokenOut(
        access_token=create_access_token(user_id, email, role),
        user=UserInfoOut(
            id=user_id,
            email=email,
            full_name=info.get("full_name"),
            phone=info.get("phone"),
            avatar_url=info.get("avatar_url"),
            role=role,
            created_at=_iso(info.get("created_at")),
            first_name=info.get("first_name"),
            last_name=info.get("last_name"),
            birth_date=_iso(info.get("birth_date")),
            gender=info.get("gender"),
            national_id=info.get("national_id"),
            email_verified_at=_iso(info.get("email_verified_at")),
            phone_verified_at=_iso(info.get("phone_verified_at")),
        ),
    )


@router.post("/signup", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
async def signup(body: SignUpRequest, session: DbSession) -> TokenOut:
    email = body.email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "ایمیل معتبر نیست")

    existing = (
        await session.execute(
            text("SELECT id FROM public.users WHERE lower(email) = :email"), {"email": email}
        )
    ).first()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "این ایمیل قبلاً ثبت شده است")

    uid = await _create_user(session, email, body.password, body.full_name, body.phone)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "این ایمیل قبلاً ثبت شده است") from exc

    return await _issue_token(session, uid, email)


@router.post("/login", response_model=TokenOut)
async def login(body: SignInRequest, session: DbSession) -> TokenOut:
    email = body.email.strip().lower()
    row = (
        await session.execute(
            text("SELECT id, password_hash FROM public.users WHERE lower(email) = :email"),
            {"email": email},
        )
    ).first()
    if row is None or not verify_password(body.password, row[1]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "ایمیل یا رمز عبور اشتباه است")
    return await _issue_token(session, row[0], email)


# F2.3: one answer for every address, so the endpoint cannot tell who has an account
_FORGOT_MESSAGE = (
    "اگر این ایمیل در ساندِه حساب داشته باشد، لینک بازیابی رمز عبور به آن ارسال می‌شود."
)


@router.post("/password/forgot", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(body: ForgotPasswordRequest, session: DbSession) -> dict:
    """Email a one-time reset link if the address has an account (F2.3).

    Unknown, known and throttled addresses all get this same 202 body.
    """
    await request_reset(session, body.email)
    await session.commit()  # the email is sent after this commit
    return {"ok": True, "message": _FORGOT_MESSAGE}


@router.post("/password/reset")
async def reset_password_endpoint(body: ResetPasswordRequest, session: DbSession) -> dict:
    """Set a new password with a valid, unused, unexpired link (F2.3)."""
    try:
        await reset_password(session, body.token, body.password)
    except ResetError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "لینک بازیابی نامعتبر است یا منقضی شده است. دوباره درخواست دهید.",
        ) from exc
    await session.commit()
    return {"ok": True}


@router.patch("/me", response_model=UserInfoOut)
async def update_me(
    body: ProfileUpdateIn, user: CurrentUser, session: DbSession
) -> UserInfoOut:
    """Update the signed-in customer's profile (used by the account page).

    F5.20 clear semantics: an omitted field is unchanged, an explicit `null`
    clears one of the new optional fields, and `national_id: ""` clears it. A
    supplied national ID is checksum-validated and normalised to bare digits;
    the phone or email written here is NOT verified — only a real verification
    flow may set the *_verified_at timestamps (none exists yet, F5.20 decision).
    The pre-F5.20 fields (`full_name`, `phone`, `avatar_url`) keep their old
    "null = unchanged" behaviour so every existing caller stays valid.
    """
    sets: list[str] = []
    params: dict = {"uid": str(user.id)}
    sent = body.model_fields_set
    if body.full_name is not None:
        sets.append("full_name = :full_name")
        params["full_name"] = body.full_name
    if body.phone is not None:
        sets.append("phone = :phone")
        params["phone"] = body.phone
    if body.avatar_url is not None:
        sets.append("avatar_url = :avatar_url")
        params["avatar_url"] = body.avatar_url
    # F5.20 fields: `in sent` distinguishes omitted (unchanged) from null (cleared).
    # When first/last are sent (and the request does not also set full_name
    # explicitly), full_name is re-derived from the merged result so checkout,
    # the account header and the admin lists never show a stale name.
    for column in ("first_name", "last_name", "gender"):
        if column in sent:
            sets.append(f"{column} = :{column}")
            params[column] = getattr(body, column)
    if ("first_name" in sent or "last_name" in sent) and "full_name" not in sent:
        first = (
            ":first_name" if "first_name" in sent
            else "COALESCE(first_name, '')"
        )
        last = (
            ":last_name" if "last_name" in sent
            else "COALESCE(last_name, '')"
        )
        if "first_name" not in sent:
            params["first_name"] = body.first_name
        if "last_name" not in sent:
            params["last_name"] = body.last_name
        sets.append(
            "full_name = btrim(COALESCE(" + first + ", '') || ' ' || "
            "COALESCE(" + last + ", ''), ' ')"
        )
    if "birth_date" in sent:
        try:
            params["birth_date"] = normalize_birth_date(body.birth_date)
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
        sets.append("birth_date = :birth_date")
    if "national_id" in sent:
        try:
            # "" / null normalise to None = cleared; otherwise validated digits
            params["national_id"] = normalize_national_id(body.national_id)
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
        sets.append("national_id = :national_id")
    if sets:
        await session.execute(
            text(f"UPDATE public.profiles SET {', '.join(sets)} WHERE id = :uid"), params
        )
        await session.commit()
    return await me(user, session)


@router.get("/me", response_model=UserInfoOut)
async def me(user: CurrentUser, session: DbSession) -> UserInfoOut:
    info = await _load_user(session, user.id)
    if info is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "کاربر پیدا نشد")
    role = await resolve_role(session, user.id)
    return UserInfoOut(
        id=user.id,
        email=info["email"],
        full_name=info["full_name"],
        phone=info["phone"],
        avatar_url=info["avatar_url"],
        role=role,
        created_at=_iso(info["created_at"]),
        first_name=info["first_name"],
        last_name=info["last_name"],
        birth_date=_iso(info["birth_date"]),
        gender=info["gender"],
        national_id=info["national_id"],
        email_verified_at=_iso(info["email_verified_at"]),
        phone_verified_at=_iso(info["phone_verified_at"]),
    )


async def _create_user(
    session, email: str, password: str, full_name: str | None, phone: str | None
):
    result = await session.execute(
        text(
            "INSERT INTO public.users (email, password_hash) "
            "VALUES (:email, :hash) RETURNING id"
        ),
        {"email": email, "hash": hash_password(password)},
    )
    uid = result.scalar_one()

    await session.execute(
        text("INSERT INTO public.profiles (id, full_name, phone) VALUES (:uid, :name, :phone)"),
        {"uid": str(uid), "name": full_name, "phone": phone},
    )
    await session.execute(
        text("INSERT INTO public.user_roles (user_id, role) VALUES (:uid, 'customer')"),
        {"uid": str(uid)},
    )
    return uid
