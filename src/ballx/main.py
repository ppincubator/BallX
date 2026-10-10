from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ballx.api.routes import router
from ballx.domain.services import DomainError


def create_app() -> FastAPI:
    app = FastAPI(title="BallX GPID", version="0.1.0")
    app.include_router(router)

    @app.exception_handler(DomainError)
    async def domain_error(request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    return app


app = create_app()
