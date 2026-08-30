package okapi.authz_test

import rego.v1

import data.okapi.authz

clinician_reads_phi := {
	"actor": {
		"sub": "u1",
		"role": "clinician",
		"actor_type": "human",
		"attributes": {"clearance_level": 3, "department": "cardiology"},
		"acting_on_behalf_of": null,
	},
	"action": "read",
	"field_key": "patient.diagnosis",
	"document_metadata": {"field_category": "phi", "requires_signoff": true},
}

ai_reads_phi := json.patch(clinician_reads_phi, [{
	"op": "replace",
	"path": "/actor",
	"value": {
		"sub": "svc",
		"role": "ai_agent",
		"actor_type": "ai_agent",
		"attributes": {"clearance_level": 3},
		"acting_on_behalf_of": null,
	},
}])

researcher_writes := json.patch(clinician_reads_phi, [
	{"op": "replace", "path": "/actor/role", "value": "researcher"},
	{"op": "replace", "path": "/action", "value": "write"},
	{"op": "replace", "path": "/document_metadata/field_category", "value": "research"},
])

test_clinician_can_read_phi if {
	authz.allow with input as clinician_reads_phi
}

test_ai_agent_blocked_from_phi_by_compliance if {
	not authz.allow with input as ai_reads_phi
}

test_researcher_cannot_write if {
	not authz.allow with input as researcher_writes
}

test_result_shape_on_allow if {
	r := authz.result with input as clinician_reads_phi
	r.allow == true
	r.allowed_fields == ["patient.diagnosis"]
}

test_result_shape_on_deny if {
	r := authz.result with input as ai_reads_phi
	r.allow == false
	r.allowed_fields == []
}
