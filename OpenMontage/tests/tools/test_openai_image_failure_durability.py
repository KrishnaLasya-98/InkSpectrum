"""Known provider rejection must not be recorded as an uncertain charged job."""
from tools.graphics.openai_image import OpenAIImage


class AuthenticationError(Exception):
    status_code = 401
    request_id = "req-auth-test"


class BadRequestError(Exception):
    status_code = 400
    request_id = "req-bad-test"


class APITimeoutError(Exception):
    status_code = None
    request_id = None


class APIConnectionError(Exception):
    status_code = None
    request_id = None


def test_authentication_failure_is_known_provider_rejection():
    details = OpenAIImage._failure_details(AuthenticationError("invalid key"))
    assert details == {
        "failure_disposition": "provider_rejected",
        "error_type": "AuthenticationError",
        "status_code": 401,
        "request_id": "req-auth-test",
    }


def test_bad_request_is_known_provider_rejection():
    assert OpenAIImage._failure_details(BadRequestError("bad prompt"))["failure_disposition"] == "provider_rejected"


def test_timeout_remains_indeterminate():
    assert OpenAIImage._failure_details(APITimeoutError("timeout"))["failure_disposition"] == "submission_unknown"


def test_connection_failure_remains_indeterminate():
    assert OpenAIImage._failure_details(APIConnectionError("network"))["failure_disposition"] == "submission_unknown"
