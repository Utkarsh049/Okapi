# HIPAA compliance regime (45 CFR § 164.502 / § 164.514).
# Pluggable policy rules loaded by the Verification & Compliance Gate.
package okapi.compliance.hipaa

import rego.v1

# Permissive by default; the rules below carve out specific regulatory denials.
default allow := true

# Rule 1: AI agents may NOT read PHI unless delegated by a named human clinician.
allow := false if {
	input.actor.actor_type == "ai_agent"
	input.document_metadata.field_category == "phi"
	is_null(input.actor.acting_on_behalf_of)
}

# Rule 2: Minimum Necessary Rule — Researchers cannot access PHI without IRB waiver or de-identification.
allow := false if {
	input.actor.role == "researcher"
	input.document_metadata.field_category == "phi"
	not input.document_metadata.deidentified
	not input.document_metadata.irb_waiver
}

# Rule 3: Business Associate Rule — Contractors cannot access PHI without active BAA metadata.
allow := false if {
	input.actor.attributes.employment_type == "contractor"
	input.document_metadata.field_category == "phi"
	not input.document_metadata.baa_active
}
