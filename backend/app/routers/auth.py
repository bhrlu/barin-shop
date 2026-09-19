"""Own auth endpoints: signup, signin, and current-user profile.

Replaces Supabase Auth. Passwords are bcrypt-hashed; sessions are HS256 JWTs
issued by this service. On signup the profile row and default 'customer' role
are created in the same transaction (mirrors the old handle_new_user trigger).
"""

import logging
import re

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.auth import CurrentUser, DbSession
from app.schemas import (
    ProfileUpdateIn,
    SignInRequest,
    SignUpRequest,
    TokenOut,
    UserInfoOut,
)
from app.security import create_access_token, hash_password, verify_password
from app.services.roles import resolve_role

log = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


async def _load_user(session, user_id) -> dict | None:
    row = (
        await session.execute(
            text(
                "SELECT p.id, u.email, p.full_name, p.phone, p.avatar_url, p.created_at "
                "FROM public.profiles p JOIN public.users u ON u.id = p.id WHERE p.id = :uid"
            ),
            {"uid": str(user_id)},
        )
    ).mappings().first()
    return dict(row) if row else None


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
            created_at=info.get("created_at").isoformat() if info.get("created_at") else None,
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


@router.patch("/me", response_model=UserInfoOut)
async def update_me(
    body: ProfileUpdateIn, user: CurrentUser, session: DbSession
) -> UserInfoOut:
    """Update the signed-in customer's profile (used by the account page)."""
    sets: list[str] = []
    params: dict = {"uid": str(user.id)}
    if body.full_name is not None:
        sets.append("full_name = :full_name")
        params["full_name"] = body.full_name
    if body.phone is not None:
        sets.append("phone = :phone")
        params["phone"] = body.phone
    if body.avatar_url is not None:
        sets.append("avatar_url = :avatar_url")
        params["avatar_url"] = body.avatar_url
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
        created_at=info["created_at"].isoformat() if info["created_at"] else None,
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
