# Structural role-based access control (architecture doc section 6.1).
# Input is a PolicyInput: {actor:{role,actor_type,attributes,...}, action, field_key,
# document_metadata:{field_category, requires_signoff, ...}}.
package okapi.rbac

import rego.v1

default allow := false

# Compliance officers may read or sign off on any field.
allow if {
	input.actor.role == "compliance_officer"
	input.action in {"read", "signoff"}
}

# Clinicians may read, write, and sign off on clinical / PHI fields.
allow if {
	input.actor.role == "clinician"
	input.action in {"read", "write", "signoff"}
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

# Quality auditors and manufacturing chemists may read, write, and sign off on compliance fields.
allow if {
	input.actor.role in {"auditor", "chemist"}
	input.action in {"read", "write", "signoff"}
	input.document_metadata.field_category == "compliance"
}

# Only compliance officers may update a document's compliance metadata
# (consent status, batch status, minor/SAE flags, etc.).
allow if {
	input.actor.role == "compliance_officer"
	input.action == "manage_compliance"
}
