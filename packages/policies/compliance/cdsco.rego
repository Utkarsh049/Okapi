# CDSCO Compliance Regime (Good Manufacturing & Clinical Practices — Schedule M & Y).
# Governs pharmaceutical batch manufacturing records and clinical trial audit trails.
package okapi.compliance.cdsco

import rego.v1

# Permissive by default; rules enforce pharmaceutical manufacturing and trial integrity.
default allow := true

# Rule 1: Post-Release Batch Immutability (Schedule M § 17.5)
# Once a batch/lot is marked 'released', 'recalled', or 'quarantined', no further writes are permitted.
allow := false if {
	input.action == "write"
	input.document_metadata.batch_status in {"released", "recalled", "quarantined"}
}

# Rule 2: Qualified Batch Release Authorization (Schedule M § 18.2)
# Releasing or signing off on lot release fields requires compliance officer or QA lead clearance >= 4.
allow := false if {
	input.action == "signoff"
	input.document_metadata.is_lot_release == true
	clearance := object.get(input.actor.attributes, "clearance_level", 0)
	clearance < 4
}

# Rule 3: Clinical Trial SAE Protection (Schedule Y § 3)
# Serious Adverse Event records cannot be updated by junior staff (clearance < 3).
allow := false if {
	input.action == "write"
	input.document_metadata.is_sae == true
	clearance := object.get(input.actor.attributes, "clearance_level", 0)
	clearance < 3
}
