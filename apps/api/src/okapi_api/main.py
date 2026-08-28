"""FastAPI application entrypoint.

HTTP concerns only: instantiate the app, register routers, expose a health probe.
Every request enters at Layer 2 (the Gate); no domain logic lives here
(architecture doc sections 2 and 3).
"""

from fastapi import FastAPI

from okapi_api.api.v1 import audit, documents, fields, forms
from okapi_api.core.logging import configure_logging
from okapi_shared.constants import API_V1_PREFIX

configure_logging()

app = FastAPI(title="Okapi", version="0.1.0")

app.include_router(documents.router, prefix=API_V1_PREFIX)
app.include_router(fields.router, prefix=API_V1_PREFIX)
app.include_router(forms.router, prefix=API_V1_PREFIX)
app.include_router(audit.router, prefix=API_V1_PREFIX)


@app.get("/health", tags=["meta"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
