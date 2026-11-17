"""
Public booking endpoints (no login). Everything a visitor sends is validated here:
the database never accepts anonymous writes, only this service does, with the service key.
"""
import hashlib
import hmac
import os
import re
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from supabase import create_client

load_dotenv()
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
# secret used to hash IPs (we never store a raw IP). Optional in .env: BOOKING_HASH_KEY
HASH_KEY = (os.environ.get("BOOKING_HASH_KEY") or os.environ["SUPABASE_SERVICE_KEY"]).encode()

router = APIRouter(prefix="/public", tags=["public"])

MAX_PER_IP_HOUR = 3       # requests from one IP per hour
MAX_PER_PHONE_DAY = 2     # requests with the same phone, for the same doctor, per day
MAX_PENDING = 100         # unhandled requests a doctor can hold before the form closes
MAX_DAYS_AHEAD = 60

SLUG_RE = re.compile(r"^[a-z0-9-]{3,40}$")
PHONE_RE = re.compile(r"^[+0-9 ()./-]{6,30}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


def clean(v):
    return CONTROL_RE.sub(" ", v).strip() if isinstance(v, str) else v


class BookingIn(BaseModel):
    slug: str
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    phone: str
    email: str | None = Field(default=None, max_length=120)
    preferred_date: date
    preferred_slot: Literal["morning", "afternoon", "any"] = "any"
    note: str = Field(default="", max_length=300)
    consent: bool
    website: str = ""   # honeypot: hidden in the page, humans never fill it

    @field_validator("first_name", "last_name", "phone", "note", "email", mode="before")
    @classmethod
    def _clean(cls, v):
        return clean(v)

    @field_validator("phone")
    @classmethod
    def _phone(cls, v):
        if not PHONE_RE.match(v):
            raise ValueError("invalid phone")
        return v

    @field_validator("email")
    @classmethod
    def _email(cls, v):
        if not v:
            return None
        if not EMAIL_RE.match(v):
            raise ValueError("invalid email")
        return v


def open_doctor(slug: str) -> dict:
    # same answer for "unknown" and "closed", so the link reveals nothing
    if not SLUG_RE.match(slug):
        raise HTTPException(404, "Lien invalide")
    r = (sb.table("profiles")
         .select("id, full_name, name_ar, title_fr, title_ar, practice_name, practice_address, practice_phone")
         .eq("booking_slug", slug).eq("booking_open", True).in_("role", ["doctor", "admin"])         .limit(1).execute())
    if not r.data:
        raise HTTPException(404, "Lien invalide")
    return r.data[0]


@router.get("/doctors/{slug}")
def public_doctor(slug: str):
    d = open_doctor(slug)
    d.pop("id")   # only what is already printed on a prescription letterhead
    return d


def recent_count(since: datetime, **eq) -> int:
    q = sb.table("booking_requests").select("id", count="exact").gte("created_at", since.isoformat())
    for k, v in eq.items():
        q = q.eq(k, v)
    return q.limit(1).execute().count or 0


@router.post("/bookings")
def create_booking(body: BookingIn, request: Request):
    if body.website.strip():
        return {"ok": True}          # bot: pretend it worked, store nothing
    if not body.consent:
        raise HTTPException(422, "Le consentement est requis.")
    today = date.today()
    if not (today <= body.preferred_date <= today + timedelta(days=MAX_DAYS_AHEAD)):
        raise HTTPException(422, "Choisissez une date dans les 60 prochains jours.")

    doctor = open_doctor(body.slug)

    # Behind a reverse proxy, run uvicorn with --proxy-headers so client.host is the real visitor IP.
    ip = request.client.host if request.client else "unknown"
    client_hash = hmac.new(HASH_KEY, ip.encode(), hashlib.sha256).hexdigest()

    now = datetime.now(timezone.utc)
    if recent_count(now - timedelta(hours=1), client_hash=client_hash) >= MAX_PER_IP_HOUR:
        raise HTTPException(429, "Trop de demandes. Réessayez plus tard ou appelez le cabinet.")
    if recent_count(now - timedelta(days=1), doctor_id=doctor["id"], phone=body.phone) >= MAX_PER_PHONE_DAY:
        raise HTTPException(429, "Une demande a déjà été envoyée avec ce numéro. Le cabinet vous rappellera.")
    pending = (sb.table("booking_requests").select("id", count="exact")
               .eq("doctor_id", doctor["id"]).eq("status", "pending").limit(1).execute().count or 0)
    if pending >= MAX_PENDING:
        raise HTTPException(503, "Les demandes en ligne sont momentanément indisponibles. Appelez le cabinet.")

    try:
        sb.table("booking_requests").insert({
            "doctor_id": doctor["id"],
            "first_name": body.first_name, "last_name": body.last_name,
            "phone": body.phone, "email": body.email,
            "preferred_date": body.preferred_date.isoformat(),
            "preferred_slot": body.preferred_slot,
            "note": body.note, "client_hash": client_hash,
        }).execute()
    except Exception:
        raise HTTPException(500, "Impossible d'enregistrer la demande.")
    return {"ok": True}      # nothing else is returned: no id, no doctor details


PAGE_SIZE = 12


@router.get("/doctors")
def list_doctors(q: str = "", page: int = 0):
    q = clean(q)[:60]
    page = max(0, min(page, 200))
    query = (sb.table("profiles")
             .select("full_name, name_ar, title_fr, title_ar, practice_name, practice_address, "
                     "practice_city, practice_phone, booking_slug", count="exact")
             .eq("booking_open", True).eq("booking_listed", True).in_("role", ["doctor", "admin"]))
    if q:
        term = re.sub(r"[%_,()\\*]", " ", q).strip()   # characters that mean something in a PostgREST filter
        if term:
            query = query.or_(
                f"full_name.ilike.%{term}%,practice_name.ilike.%{term}%,"
                f"practice_city.ilike.%{term}%,practice_address.ilike.%{term}%")
    res = query.order("full_name").range(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE - 1).execute()
    return {"items": res.data, "total": res.count or 0, "page_size": PAGE_SIZE}