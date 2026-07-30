from fastapi import (
    FastAPI,
    Header,
    HTTPException,
    Request,
)

from sqlalchemy import text

from starlette.middleware.gzip import (
    GZipMiddleware,
)

from app.config import settings
from app.db import engine

from app.modules.cfe.handlers import (
    process_client,
    process_provider,
)

from app.panel import (
    router as panel_router,
)

from app.admin_multibot import (
    router as multibot_router,
)

from app.webhook_utils import (
    get_instance,
    get_remote_jid,
)


app = FastAPI(
    title="Trámites Extras Bot",
    version="1.1.0",
)

app.include_router(
    panel_router
)

app.include_router(
    multibot_router
)

app.add_middleware(
    GZipMiddleware,
    minimum_size=1000,
    compresslevel=5,
)


@app.get("/health")
def health() -> dict:
    with engine.connect() as conn:
        conn.execute(
            text("SELECT 1")
        )

    return {
        "ok": True,
        "service": "tramites-extras-bot",
    }


@app.post("/webhooks/evolution")
async def evolution_webhook(
    request: Request,
    secret: str | None = None,
    x_webhook_secret: str | None = Header(
        default=None
    ),
) -> dict:
    if (
        x_webhook_secret
        or secret
    ) != settings.WEBHOOK_SECRET:
        raise HTTPException(
            status_code=401,
            detail="invalid webhook secret",
        )

    payload = await request.json()

    print(
        "EXTRAS_WEBHOOK_INPUT",
        {
            "instance":
                get_instance(payload),

            "remote_jid":
                get_remote_jid(payload),
        },
        flush=True,
    )

    provider_result = process_provider(
        payload
    )

    if not provider_result.get(
        "ignored"
    ):
        return provider_result

    return process_client(
        payload
    )
