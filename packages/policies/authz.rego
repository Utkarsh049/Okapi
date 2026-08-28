# Aggregate decision surface. PolicyClient reads data.okapi.authz.result
# (see OPA_DECISION_PATH in okapi_shared.constants).
package okapi.authz

import rego.v1

import data.okapi.abac
import data.okapi.rbac

default allow := false

# Deny-by-default skeleton: real grants land in rbac.rego / abac.rego during
# implementation. Structural checks (RBAC + ABAC) must both pass.
allow if {
	rbac.allow
	abac.allow
}

reason := "granted by rbac+abac" if allow

reason := "denied by default policy" if not allow

result := {
	"allow": allow,
	"allowed_fields": [],
	"reason": reason,
}
