from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException


class APIError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status = status
        self.code = code
        self.message = message


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def api_error(request: Request, exc: APIError):
        headers = {"WWW-Authenticate": "Bearer"} if exc.status == 401 else None
        return JSONResponse(
            {"code": exc.code, "message": exc.message},
            status_code=exc.status,
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        messages = []
        for error in exc.errors():
            location = ".".join(str(part) for part in error["loc"] if part != "body")
            messages.append(f"{location}: {error['msg']}")
        return JSONResponse(
            {"code": "validation", "message": "; ".join(messages)}, status_code=422
        )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        codes = {401: "invalid_token", 403: "forbidden", 404: "not_found",
                 409: "conflict", 422: "validation"}
        return JSONResponse(
            {"code": codes.get(exc.status_code, "server" if exc.status_code >= 500 else "validation"),
             "message": str(exc.detail)},
            status_code=exc.status_code,
            headers=exc.headers,
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error(request: Request, exc: IntegrityError):
        return JSONResponse(
            {"code": "conflict", "message": "The record conflicts with an existing record."},
            status_code=409,
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        import logging

        logging.getLogger(__name__).exception("Unhandled API error", exc_info=exc)
        return JSONResponse(
            {"code": "server", "message": "An unexpected server error occurred."},
            status_code=500,
        )
