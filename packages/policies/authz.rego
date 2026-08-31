# Aggregate decision surface. PolicyClient reads data.okapi.authz.result
# (see OPA_DECISION_PATH in okapi_shared.constants).
package okapi.authz

import rego.v1

import data.okapi.abac
import data.okapi.compliance.cdsco
import data.okapi.compliance.dpdp
import data.okapi.compliance.hipaa
import data.okapi.rbac

default allow := false

# A field-scoped action is allowed only if structural (RBAC), attribute (ABAC),
# and all active compliance regimes (HIPAA, DPDP, CDSCO) agree.
allow if {
	rbac.allow
	abac.allow
	hipaa.allow
	dpdp.allow
	cdsco.allow
}

reason := "allowed by rbac + abac + compliance (hipaa, dpdp, cdsco)" if allow

reason := sprintf(
	"denied (rbac=%v abac=%v hipaa=%v dpdp=%v cdsco=%v)",
	[rbac.allow, abac.allow, hipaa.allow, dpdp.allow, cdsco.allow],
) if {
	not allow
}

allowed_fields := [input.field_key] if allow

allowed_fields := [] if not allow

result := {
	"allow": allow,
	"allowed_fields": allowed_fields,
	"reason": reason,
}
