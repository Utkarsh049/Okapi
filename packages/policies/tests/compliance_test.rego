package okapi.compliance_test

import rego.v1

import data.okapi.authz

# Base input fixture for a clinician accessing clinical data
base_clinician_input := {
	"actor": {
		"sub": "u1",
		"role": "clinician",
		"actor_type": "human",
		"attributes": {"clearance_level": 3, "department": "cardiology", "employment_type": "full_time"},
		"acting_on_behalf_of": null,
	},
	"action": "read",
	"field_key": "patient.care_plan",
	"document_metadata": {"field_category": "clinical", "requires_signoff": false},
}

# --- HIPAA Regime Tests -----------------------------------------------------

test_hipaa_contractor_without_baa_denied if {
	contractor_input := json.patch(base_clinician_input, [
		{"op": "replace", "path": "/actor/attributes/employment_type", "value": "contractor"},
		{"op": "replace", "path": "/field_key", "value": "patient.diagnosis"},
		{"op": "replace", "path": "/document_metadata/field_category", "value": "phi"},
	])
	not authz.allow with input as contractor_input
}

test_hipaa_contractor_with_baa_allowed if {
	contractor_with_baa := json.patch(base_clinician_input, [
		{"op": "replace", "path": "/actor/attributes/employment_type", "value": "contractor"},
		{"op": "replace", "path": "/field_key", "value": "patient.diagnosis"},
		{"op": "replace", "path": "/document_metadata/field_category", "value": "phi"},
		{"op": "add", "path": "/document_metadata/baa_active", "value": true},
	])
	authz.allow with input as contractor_with_baa
}

test_hipaa_ai_agent_delegated_allowed if {
	ai_delegated := json.patch(base_clinician_input, [
		{"op": "replace", "path": "/actor", "value": {
			"sub": "svc-1",
			"role": "ai_agent",
			"actor_type": "ai_agent",
			"attributes": {"clearance_level": 3},
			"acting_on_behalf_of": "dr_casey_lin",
		}},
		{"op": "replace", "path": "/field_key", "value": "patient.diagnosis"},
		{"op": "replace", "path": "/document_metadata/field_category", "value": "phi"},
	])
	authz.allow with input as ai_delegated
}

# --- DPDP Regime Tests ------------------------------------------------------

test_dpdp_consent_withdrawn_blocks_clinician if {
	withdrawn_input := json.patch(base_clinician_input, [
		{"op": "add", "path": "/document_metadata/consent_status", "value": "withdrawn"},
	])
	not authz.allow with input as withdrawn_input
}

test_dpdp_consent_withdrawn_allows_compliance_officer if {
	compliance_input := json.patch(base_clinician_input, [
		{"op": "replace", "path": "/actor/role", "value": "compliance_officer"},
		{"op": "add", "path": "/document_metadata/consent_status", "value": "withdrawn"},
	])
	authz.allow with input as compliance_input
}

test_dpdp_purpose_mismatch_denied if {
	purpose_mismatch_input := json.patch(base_clinician_input, [
		{"op": "add", "path": "/actor/attributes/purpose", "value": "marketing"},
		{"op": "add", "path": "/document_metadata/consent_purposes", "value": ["treatment", "clinical_trials"]},
	])
	not authz.allow with input as purpose_mismatch_input
}

test_dpdp_minor_without_parental_consent_denied if {
	minor_input := json.patch(base_clinician_input, [
		{"op": "add", "path": "/document_metadata/is_minor", "value": true},
		{"op": "replace", "path": "/actor/attributes/clearance_level", "value": 2},
	])
	not authz.allow with input as minor_input
}

test_dpdp_minor_with_parental_consent_allowed if {
	minor_with_consent := json.patch(base_clinician_input, [
		{"op": "add", "path": "/document_metadata/is_minor", "value": true},
		{"op": "add", "path": "/document_metadata/parental_consent", "value": true},
	])
	authz.allow with input as minor_with_consent
}

# --- CDSCO Regime Tests -----------------------------------------------------

test_cdsco_released_batch_write_denied if {
	released_batch_write := json.patch(base_clinician_input, [
		{"op": "replace", "path": "/action", "value": "write"},
		{"op": "add", "path": "/document_metadata/batch_status", "value": "released"},
	])
	not authz.allow with input as released_batch_write
}

test_cdsco_lot_release_low_clearance_signoff_denied if {
	junior_lot_signoff := json.patch(base_clinician_input, [
		{"op": "replace", "path": "/action", "value": "signoff"},
		{"op": "add", "path": "/document_metadata/is_lot_release", "value": true},
		{"op": "replace", "path": "/actor/attributes/clearance_level", "value": 2},
	])
	not authz.allow with input as junior_lot_signoff
}

test_cdsco_lot_release_high_clearance_signoff_allowed if {
	senior_lot_signoff := json.patch(base_clinician_input, [
		{"op": "replace", "path": "/actor/role", "value": "compliance_officer"},
		{"op": "replace", "path": "/action", "value": "signoff"},
		{"op": "add", "path": "/document_metadata/is_lot_release", "value": true},
		{"op": "replace", "path": "/actor/attributes/clearance_level", "value": 5},
	])
	authz.allow with input as senior_lot_signoff
}
