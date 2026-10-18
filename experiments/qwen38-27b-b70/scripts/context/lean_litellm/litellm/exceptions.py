"""litellm's exception names for the lean stand-in (see __init__.py). Messages read `litellm.<Name>: <text>` as
litellm's do, so the harness's context-overflow test and the run records see the same strings."""
from __future__ import annotations


class APIError(Exception):
    status_code = 500

    def __init__(self, message: str = "", model: str | None = None, llm_provider: str = "openai", **_):
        self.message = f"litellm.{type(self).__name__}: {message}"
        self.llm_provider = llm_provider
        self.model = model
        super().__init__(self.message)


class BadRequestError(APIError):
    status_code = 400


class ContextWindowExceededError(BadRequestError):
    pass


class UnsupportedParamsError(BadRequestError):
    pass


class AuthenticationError(APIError):
    status_code = 401


class PermissionDeniedError(APIError):
    status_code = 403


class NotFoundError(APIError):
    status_code = 404


class Timeout(APIError):
    status_code = 408


class UnprocessableEntityError(APIError):
    status_code = 422


class RateLimitError(APIError):
    status_code = 429


class InternalServerError(APIError):
    status_code = 500


class BadGatewayError(APIError):
    status_code = 502


class ServiceUnavailableError(APIError):
    status_code = 503


class APIConnectionError(APIError):
    status_code = 500
