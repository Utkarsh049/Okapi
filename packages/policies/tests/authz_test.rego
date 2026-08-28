package okapi.authz_test

import rego.v1

import data.okapi.authz

test_deny_by_default if {
	authz.allow == false with input as {}
}

test_result_shape_present if {
	result := authz.result with input as {}
	result.allow == false
	result.reason == "denied by default policy"
}
