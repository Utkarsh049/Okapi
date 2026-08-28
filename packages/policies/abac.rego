# Attribute-based access control (architecture doc section 6).
# Keys off input.actor.attributes (department, clearance_level, employment_type).
# Deny-by-default skeleton; rule bodies land here during implementation.
package okapi.abac

import rego.v1

default allow := false
