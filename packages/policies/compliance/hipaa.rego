# HIPAA compliance regime (architecture doc section 6.1).
# One file per regime keeps rules pluggable and centrally updatable.
package okapi.compliance.hipaa

import rego.v1

# Permissive by default; the rules below carve out denials.
default allow := true

# An AI agent may not read PHI unless it is acting on behalf of a named human.
allow := false if {
	input.actor.actor_type == "ai_agent"
	input.document_metadata.field_category == "phi"
	is_null(input.actor.acting_on_behalf_of)
}
