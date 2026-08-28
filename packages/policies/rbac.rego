# Structural role-based access control (architecture doc section 6.1).
# Deny-by-default skeleton; rule bodies land here during implementation.
package okapi.rbac

import rego.v1

default allow := false
