"""AI-assisted form endpoints (architecture doc sections 5.3 and 9).

Endpoints:
- POST /forms/{form_id}/autofill: Gated AI auto-completion from source documents.
- POST /forms/{form_id}/submit: Submission endpoint blocked if any field is in pending_signoff.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from okapi_api.core.deps import (
    CurrentActor,
    get_form_fill_service,
)
from okapi_api.schemas.form import (
    FormAutofillRequest,
    FormAutofillResponse,
    FormSubmitResponse,
)
from okapi_api.services.form_fill_service import FormFillService

router = APIRouter(prefix="/forms", tags=["forms"])


@router.post("/{form_id}/autofill", response_model=FormAutofillResponse)
def autofill_form(
    form_id: uuid.UUID,
    body: FormAutofillRequest,
    actor: CurrentActor,
    form_service: Annotated[FormFillService, Depends(get_form_fill_service)],
) -> FormAutofillResponse:
    return form_service.autofill_form(
        actor=actor,
        form_document_id=form_id,
        source_document_ids=body.source_document_ids,
        target_field_keys=body.target_field_keys,
    )


@router.post("/{form_id}/submit", response_model=FormSubmitResponse)
def submit_form(
    form_id: uuid.UUID,
    actor: CurrentActor,
    form_service: Annotated[FormFillService, Depends(get_form_fill_service)],
) -> FormSubmitResponse:
    return form_service.submit_form(actor=actor, form_document_id=form_id)
