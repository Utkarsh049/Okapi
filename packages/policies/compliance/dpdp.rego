# DPDP Compliance Regime (India Digital Personal Data Protection Act 2023).
# Enforces Purpose Limitation (Sec 6), Consent Withdrawal (Sec 6(4)), and Children's Data Protection (Sec 9).
package okapi.compliance.dpdp

import rego.v1

# Permissive by default; rules carve out statutory denials.
default allow := true

# Rule 1: Consent Withdrawal (DPDP Sec 6(4))
# If consent is withdrawn, block all access except for compliance/legal audit.
allow := false if {
	input.document_metadata.consent_status == "withdrawn"
	input.actor.role != "compliance_officer"
}

# Rule 2: Purpose Limitation (DPDP Sec 6)
# If consent specifies explicit allowable purposes, actor's purpose must match.
allow := false if {
	# Only applies if specific consent purposes are registered on the record
	is_array(input.document_metadata.consent_purposes)
	count(input.document_metadata.consent_purposes) > 0

	# Get actor purpose from attributes or derive from role
	actor_purpose := object.get(input.actor.attributes, "purpose", input.actor.role)
	not actor_purpose in input.document_metadata.consent_purposes
	input.actor.role != "compliance_officer"
}

# Rule 3: Protection of Children's Personal Data (DPDP Sec 9)
# Processing personal data of minors requires verified parental consent or supervisor clearance.
allow := false if {
	input.document_metadata.is_minor == true
	not input.document_metadata.parental_consent
	input.actor.role != "compliance_officer"
	clearance := object.get(input.actor.attributes, "clearance_level", 0)
	clearance < 4
}
