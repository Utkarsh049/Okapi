# Structural role-based access control (architecture doc section 6.1).
# Input is a PolicyInput: {actor:{role,actor_type,attributes,...}, action, field_key,
# document_metadata:{field_category, requires_signoff, ...}}.
package okapi.rbac

import rego.v1

default allow := false

# Compliance officers may read any field.
allow if {
	input.actor.role == "compliance_officer"
	input.action == "read"
}

# Clinicians may read and write clinical / PHI fields.
allow if {
	input.actor.role == "clinician"
	input.action in {"read", "write"}
	input.document_metadata.field_category in {"clinical", "phi"}
}

# Researchers may read research fields only.
allow if {
	input.actor.role == "researcher"
	input.action == "read"
	input.document_metadata.field_category == "research"
}

# AI agents may read (PHI is further restricted by the compliance layer).
allow if {
	input.actor.role == "ai_agent"
	input.action == "read"
}
