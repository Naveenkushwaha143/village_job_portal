from __future__ import annotations

import hashlib
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote_plus, urlencode
from uuid import uuid4

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from .service import VillageJobPortalService


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))
SESSION_COOKIE = "vjp_session"
GOOGLE_STATE_COOKIE = "vjp_google_oauth_state"
GOOGLE_NEXT_COOKIE = "vjp_google_oauth_next"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"


class SMSRequest(BaseModel):
    from_phone: str = Field(..., min_length=10, max_length=20)
    message: str = Field(..., min_length=3, max_length=280)


class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    phone: str = Field(..., min_length=10, max_length=20)
    skill: str = Field(..., min_length=2, max_length=80)
    village: str = Field(..., min_length=2, max_length=80)
    age: int = Field(28, ge=18, le=80)
    hourly_rate: float = Field(120.0, gt=0)
    daily_rate: float = Field(850.0, gt=0)
    image_url: str = Field("", max_length=500)
    availability_status: str = Field("free", pattern="^(free|working)$")
    working_start_time: str = Field("09:00", min_length=4, max_length=8)
    working_end_time: str = Field("18:00", min_length=4, max_length=8)
    next_free_at: str = Field("", max_length=60)


def get_db_path() -> Path:
    return Path(os.getenv("VILLAGE_JOB_PORTAL_DB", "data/village_jobs.db"))


def get_google_oauth_config() -> tuple[str, str] | None:
    client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        return None
    return client_id, client_secret


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000).hex()
    return f"{salt}${digest}"


def verify_password(password: str, stored_hash: str) -> bool:
    if "$" not in stored_hash:
        # Backward-compatible fallback for seeded demo admin
        return password == stored_hash

    salt, digest = stored_hash.split("$", 1)
    check = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000).hex()
    return secrets.compare_digest(check, digest)


def get_current_user(request: Request, service: VillageJobPortalService) -> dict[str, object] | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    return service.get_user_by_session_token(token)


def build_home_context(
    request: Request,
    service: VillageJobPortalService,
    current_user: dict[str, object] | None,
    search_result: str | None = None,
    register_result: str | None = None,
    booking_result: str | None = None,
    sms_preview: dict[str, str | None] | None = None,
    filters: dict[str, object] | None = None,
) -> dict[str, object]:
    active_filters = {
        "skill": "",
        "village": "",
        "min_rating": "",
        "max_hourly_rate": "",
    }
    if filters:
        active_filters.update(filters)

    min_rating = None
    max_hourly_rate = None
    try:
        if str(active_filters["min_rating"]).strip():
            min_rating = float(str(active_filters["min_rating"]))
    except ValueError:
        active_filters["min_rating"] = ""

    try:
        if str(active_filters["max_hourly_rate"]).strip():
            max_hourly_rate = float(str(active_filters["max_hourly_rate"]))
    except ValueError:
        active_filters["max_hourly_rate"] = ""

    workers = service.list_workers(
        limit=12,
        skill=str(active_filters["skill"]).strip() or None,
        village=str(active_filters["village"]).strip() or None,
        min_rating=min_rating,
        max_hourly_rate=max_hourly_rate,
    )
    return {
        "request": request,
        "skills": service.supported_skills(),
        "skill_hi_map": service.skill_hindi_labels(),
        "search_result": search_result,
        "register_result": register_result,
        "booking_result": booking_result,
        "sms_preview": sms_preview,
        "workers": workers,
        "worker_count": len(workers),
        "filters": active_filters,
        "current_user": current_user,
    }


async def save_uploaded_image(upload: UploadFile | None, prefix: str) -> str:
    if upload is None or not upload.filename:
        return ""

    content_type = upload.content_type or ""
    if not content_type.startswith("image/"):
        return ""

    suffix = Path(upload.filename).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = ".jpg"

    upload_dir = BASE_DIR / "static" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_name = f"{prefix}-{uuid4().hex[:12]}{suffix}"
    target = upload_dir / file_name
    data = await upload.read()
    target.write_bytes(data)
    return f"/static/uploads/{file_name}"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_path = get_db_path()
    service = VillageJobPortalService(db_path=db_path)
    service.initialize(seed=not db_path.exists())
    app.state.service = service
    yield


app = FastAPI(
    title="Village Job Portal",
    description="SMS-based skill and labor directory for villages",
    version="0.1.0",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    service: VillageJobPortalService = request.app.state.service
    current_user = get_current_user(request, service)
    filter_payload = {
        "skill": request.query_params.get("skill", ""),
        "village": request.query_params.get("village", ""),
        "min_rating": request.query_params.get("min_rating", ""),
        "max_hourly_rate": request.query_params.get("max_hourly_rate", ""),
    }
    context = build_home_context(request, service, current_user=current_user, filters=filter_payload)
    return TEMPLATES.TemplateResponse(request=request, name="index.html", context=context)


@app.post("/search", response_class=HTMLResponse)
async def search_workers(
    request: Request,
    message: str = Form(...),
    from_phone: str = Form("9876500000"),
    booking_image: UploadFile | None = File(None),
) -> HTMLResponse:
    service: VillageJobPortalService = request.app.state.service
    current_user = get_current_user(request, service)
    booking_image_url = await save_uploaded_image(booking_image, "booking")
    sms_preview = service.process_message(from_phone, message)
    if booking_image_url:
        sms_preview += " बुकिंग करने वाले की प्रोफाइल इमेज अपलोड हो गई है।"

    context = build_home_context(
        request,
        service,
        current_user=current_user,
        search_result=sms_preview,
        sms_preview={
            "from_phone": from_phone,
            "message": message,
            "image_url": booking_image_url,
        },
    )
    return TEMPLATES.TemplateResponse(request=request, name="index.html", context=context)


@app.post("/register", response_class=HTMLResponse)
async def register_worker(
    request: Request,
    name: str = Form(...),
    phone: str = Form(...),
    skill: str = Form(...),
    village: str = Form(...),
    age: int = Form(28),
    hourly_rate: float = Form(120.0),
    daily_rate: float = Form(850.0),
    image_url: str = Form(""),
    availability_status: str = Form("free"),
    working_start_time: str = Form("09:00"),
    working_end_time: str = Form("18:00"),
    next_free_at: str = Form(""),
    profile_image: UploadFile | None = File(None),
) -> HTMLResponse:
    service: VillageJobPortalService = request.app.state.service
    current_user = get_current_user(request, service)
    sms_message = f"REGISTER, {name}, {skill}, {village}, {phone}"
    uploaded_image = await save_uploaded_image(profile_image, "worker")
    selected_image = uploaded_image or image_url
    try:
        record = service.register_worker(
            name=name,
            phone=phone,
            skill=skill,
            location=village,
            age=age,
            hourly_rate=hourly_rate,
            daily_rate=daily_rate,
            image_url=selected_image,
            available=1 if availability_status == "free" else 0,
            working_start_time=working_start_time,
            working_end_time=working_end_time,
            next_free_at=next_free_at,
        )
        register_result = (
            f"{record.name} को {record.skill_label} के रूप में {record.village} में जोड़ दिया गया। "
            f"रेट: Rs {record.hourly_rate:.0f}/घंटा और Rs {record.daily_rate:.0f}/दिन।"
        )
    except ValueError:
        register_result = "स्किल पहचान में नहीं आई। Tractor Mechanic, Mason, Plumber, Electrician, Farm Labor या Welder लिखें।"

    context = build_home_context(
        request,
        service,
        current_user=current_user,
        register_result=register_result,
        sms_preview={
            "from_phone": phone,
            "message": sms_message,
            "image_url": selected_image,
        },
    )
    return TEMPLATES.TemplateResponse(request=request, name="index.html", context=context)


@app.post("/book/{worker_phone}")
async def book_worker(
    request: Request,
    worker_phone: str,
    notes: str = Form(""),
) -> RedirectResponse:
    service: VillageJobPortalService = request.app.state.service
    current_user = get_current_user(request, service)
    if not current_user:
        return RedirectResponse(url="/auth?mode=login&next=/", status_code=303)

    service.create_booking(worker_phone, int(current_user["id"]), notes)
    return RedirectResponse(url=f"/workers/{worker_phone}?booked=1", status_code=303)


@app.get("/workers/{phone}", response_class=HTMLResponse)
async def worker_profile(request: Request, phone: str) -> HTMLResponse:
    service: VillageJobPortalService = request.app.state.service
    profile = service.get_worker_profile(phone)
    if profile is None:
        raise HTTPException(status_code=404, detail="Worker not found")

    context = {
        "request": request,
        "profile": profile,
        "current_user": get_current_user(request, service),
        "booked": request.query_params.get("booked") == "1",
    }
    return TEMPLATES.TemplateResponse(request=request, name="worker_profile.html", context=context)


@app.get("/auth", response_class=HTMLResponse)
async def auth_page(request: Request) -> HTMLResponse:
    service: VillageJobPortalService = request.app.state.service
    current_user = get_current_user(request, service)
    if current_user:
        return RedirectResponse(url="/", status_code=303)

    context = {
        "request": request,
        "mode": request.query_params.get("mode", "login"),
        "next": request.query_params.get("next", "/"),
        "message": request.query_params.get("message", ""),
        "google_oauth_configured": get_google_oauth_config() is not None,
    }
    return TEMPLATES.TemplateResponse(request=request, name="auth.html", context=context)


@app.get("/auth/google/login")
async def auth_google_login(request: Request, next: str = "/") -> RedirectResponse:
    config = get_google_oauth_config()
    if not config:
        return RedirectResponse(
            url=f"/auth?mode=signup&next={quote_plus(next or '/')}"
            "&message=Google signup demo mode active hai. Continue with Google dabaiye.",
            status_code=303,
        )

    client_id, _ = config
    state = secrets.token_urlsafe(24)
    redirect_uri = str(request.url_for("auth_google_callback"))
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    response = RedirectResponse(url=f"{GOOGLE_AUTH_URL}?{urlencode(params)}", status_code=303)
    response.set_cookie(GOOGLE_STATE_COOKIE, state, httponly=True, samesite="lax", max_age=600)
    response.set_cookie(GOOGLE_NEXT_COOKIE, next or "/", httponly=True, samesite="lax", max_age=600)
    return response


@app.get("/auth/google-signup")
async def auth_google_signup_legacy_get(next: str = "/") -> RedirectResponse:
    # Backward-compatible URL kept for old bookmarks/links.
    return RedirectResponse(url=f"/auth/google/login?next={quote_plus(next or '/')}", status_code=303)


@app.post("/auth/google-signup")
async def auth_google_signup_legacy_post(
    request: Request,
    next: str = Form("/"),
) -> RedirectResponse:
    service: VillageJobPortalService = request.app.state.service
    config = get_google_oauth_config()

    if config:
        return RedirectResponse(url=f"/auth/google/login?next={quote_plus(next or '/')}", status_code=303)

    # One-click demo Google signup when OAuth credentials are not configured.
    demo_suffix = secrets.token_hex(4)
    normalized_email = f"google.demo.{demo_suffix}@vjp.local"
    user = service.get_user_by_email(normalized_email)
    if not user:
        random_password = secrets.token_urlsafe(16)
        user_id = service.create_user(
            "Google Demo User",
            normalized_email,
            "",
            hash_password(random_password),
            provider="google-demo",
        )
        user = service.get_user_by_id(user_id)

    if not user:
        return RedirectResponse(url="/auth?mode=signup&message=Google demo account create nahi hua", status_code=303)

    token = service.create_session(int(user["id"]))
    response = RedirectResponse(url=next or "/", status_code=303)
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax")
    return response


@app.get("/auth/google/callback")
async def auth_google_callback(request: Request, code: str = "", state: str = "", error: str = "") -> RedirectResponse:
    if error:
        return RedirectResponse(url=f"/auth?mode=login&message=Google login failed: {quote_plus(error)}", status_code=303)

    saved_state = request.cookies.get(GOOGLE_STATE_COOKIE, "")
    next_url = request.cookies.get(GOOGLE_NEXT_COOKIE, "/")
    if not saved_state or not state or saved_state != state:
        return RedirectResponse(url="/auth?mode=login&message=Invalid Google OAuth state", status_code=303)

    config = get_google_oauth_config()
    if not config:
        return RedirectResponse(url="/auth?mode=login&message=Google OAuth not configured", status_code=303)

    client_id, client_secret = config
    redirect_uri = str(request.url_for("auth_google_callback"))

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            token_resp = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            token_resp.raise_for_status()
            token_json = token_resp.json()
            id_token = str(token_json.get("id_token", ""))
            if not id_token:
                raise ValueError("Missing id_token")

            info_resp = await client.get(GOOGLE_TOKENINFO_URL, params={"id_token": id_token})
            info_resp.raise_for_status()
            id_info = info_resp.json()
    except Exception:
        return RedirectResponse(url="/auth?mode=login&message=Google token verification failed", status_code=303)

    if str(id_info.get("aud", "")) != client_id:
        return RedirectResponse(url="/auth?mode=login&message=Google token audience mismatch", status_code=303)

    email = str(id_info.get("email", "")).strip().lower()
    full_name = str(id_info.get("name", "")).strip() or "Google User"
    if not email:
        return RedirectResponse(url="/auth?mode=login&message=Google account email missing", status_code=303)

    service: VillageJobPortalService = request.app.state.service
    user = service.get_user_by_email(email)
    if not user:
        random_password = secrets.token_urlsafe(16)
        user_id = service.create_user(full_name, email, "", hash_password(random_password), provider="google")
        user = service.get_user_by_id(user_id)

    if not user:
        return RedirectResponse(url="/auth?mode=login&message=Unable to create Google account", status_code=303)

    token = service.create_session(int(user["id"]))
    response = RedirectResponse(url=next_url or "/", status_code=303)
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax")
    response.delete_cookie(GOOGLE_STATE_COOKIE)
    response.delete_cookie(GOOGLE_NEXT_COOKIE)
    return response


@app.post("/auth/signup")
async def auth_signup(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(""),
    password: str = Form(...),
    next: str = Form("/"),
) -> RedirectResponse:
    service: VillageJobPortalService = request.app.state.service
    existing = service.get_user_by_email(email)
    if existing:
        return RedirectResponse(url="/auth?mode=signup&message=Email already exists", status_code=303)

    user_id = service.create_user(full_name, email, phone, hash_password(password), provider="local")
    token = service.create_session(user_id)
    response = RedirectResponse(url=next or "/", status_code=303)
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax")
    return response


@app.post("/auth/login")
async def auth_login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
) -> RedirectResponse:
    service: VillageJobPortalService = request.app.state.service
    user = service.get_user_by_email(email)
    if not user:
        return RedirectResponse(url="/auth?mode=login&message=Invalid credentials", status_code=303)

    if not verify_password(password, str(user["password_hash"])):
        return RedirectResponse(url="/auth?mode=login&message=Invalid credentials", status_code=303)

    token = service.create_session(int(user["id"]))
    response = RedirectResponse(url=next or "/", status_code=303)
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax")
    return response


@app.post("/auth/logout")
async def auth_logout(request: Request) -> RedirectResponse:
    service: VillageJobPortalService = request.app.state.service
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        service.delete_session(token)
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request) -> HTMLResponse:
    service: VillageJobPortalService = request.app.state.service
    current_user = get_current_user(request, service)
    if not current_user:
        return RedirectResponse(url="/auth?mode=login&next=/admin/dashboard", status_code=303)

    if str(current_user.get("role", "")) != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    context = {
        "request": request,
        "current_user": current_user,
        "workers": service.list_workers(limit=100),
        "bookings": service.list_recent_bookings(limit=100),
    }
    return TEMPLATES.TemplateResponse(request=request, name="admin_dashboard.html", context=context)


@app.post("/admin/bookings/{booking_id}/progress")
async def update_booking_progress(
    request: Request,
    booking_id: int,
    progress_percent: int = Form(...),
    progress_note: str = Form(""),
    status: str = Form("in_progress"),
) -> RedirectResponse:
    service: VillageJobPortalService = request.app.state.service
    current_user = get_current_user(request, service)
    if not current_user:
        return RedirectResponse(url="/auth?mode=login&next=/admin/dashboard", status_code=303)

    if str(current_user.get("role", "")) != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    service.update_booking_progress(booking_id, progress_percent, progress_note, status)
    return RedirectResponse(url="/admin/dashboard", status_code=303)


@app.post("/api/sms")
async def sms_api(payload: SMSRequest, request: Request) -> dict[str, object]:
    service: VillageJobPortalService = request.app.state.service
    response = service.process_message(payload.from_phone, payload.message)
    return {"reply": response}


@app.post("/api/register")
async def register_api(payload: RegisterRequest, request: Request) -> dict[str, object]:
    service: VillageJobPortalService = request.app.state.service
    try:
        record = service.register_worker(
            name=payload.name,
            phone=payload.phone,
            skill=payload.skill,
            location=payload.village,
            age=payload.age,
            hourly_rate=payload.hourly_rate,
            daily_rate=payload.daily_rate,
            image_url=payload.image_url,
            available=1 if payload.availability_status == "free" else 0,
            working_start_time=payload.working_start_time,
            working_end_time=payload.working_end_time,
            next_free_at=payload.next_free_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "reply": f"Registered {record.name} as {record.skill_label} in {record.village}.",
        "worker": service.get_worker_profile(record.phone),
    }


@app.get("/api/workers/{phone}")
async def worker_profile_api(phone: str, request: Request) -> dict[str, object]:
    service: VillageJobPortalService = request.app.state.service
    profile = service.get_worker_profile(phone)
    if profile is None:
        raise HTTPException(status_code=404, detail="Worker not found")
    return {"worker": profile}


def run() -> None:
    import uvicorn

    uvicorn.run("village_job_portal.app:app", host="0.0.0.0", port=8000, reload=False)
