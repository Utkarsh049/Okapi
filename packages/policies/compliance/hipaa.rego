# HIPAA compliance regime (architecture doc section 6.1).
# One file per regime keeps rules pluggable and centrally updatable.
# Skeleton: no restrictions asserted yet.
package okapi.compliance.hipaa

import rego.v1

default allow := true
