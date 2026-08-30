"""FastAPI application entrypoint.

HTTP concerns only: instantiate the app, register routers, expose a health probe.
Every request enters at Layer 2 (the Gate); no domain logic lives here
(architecture doc sections 2 and 3).
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from okapi_api.api.v1 import audit, auth, documents, fields, forms
from okapi_api.core.logging import configure_logging
from okapi_api.core.middleware import PayloadSizeLimitMiddleware, SecurityHeadersMiddleware
from okapi_api.gate.gate import GateDenied
from okapi_shared.constants import API_V1_PREFIX

configure_logging()

app = FastAPI(title="Okapi", version="0.1.0")

# Security and payload size middlewares
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(PayloadSizeLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=API_V1_PREFIX)
app.include_router(documents.router, prefix=API_V1_PREFIX)
app.include_router(fields.router, prefix=API_V1_PREFIX)
app.include_router(forms.router, prefix=API_V1_PREFIX)
app.include_router(audit.router, prefix=API_V1_PREFIX)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    """Redirect root path to interactive Swagger documentation."""
    return RedirectResponse(url="/docs")


@app.exception_handler(GateDenied)
def _on_gate_denied(_: Request, exc: GateDenied) -> JSONResponse:
    """The deny is already recorded in audit_log by the Gate; just shape the 403."""
    return JSONResponse(status_code=403, content={"detail": exc.reason})


@app.get("/health", tags=["meta"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
