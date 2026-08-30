# Attribute-based access control (architecture doc section 6).
# Keys off input.actor.attributes (clearance_level, department, ...).
package okapi.abac

import rego.v1

default allow := false

# Minimum clearance required to touch a field, by category.
_required_clearance := {"phi": 3, "clinical": 2, "research": 1}

allow if {
	required := object.get(_required_clearance, input.document_metadata.field_category, 0)
	input.actor.attributes.clearance_level >= required
}
