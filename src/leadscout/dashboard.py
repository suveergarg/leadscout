from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from leadscout.store import Store

_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def create_app(store: Store) -> FastAPI:
    app = FastAPI(title="leadscout")

    @app.get("/")
    def index(request: Request, show_dismissed: bool = False):
        leads = store.list_leads(include_dismissed=show_dismissed)
        return _TEMPLATES.TemplateResponse(
            request, "leads.html", {"leads": leads, "show_dismissed": show_dismissed}
        )

    @app.post("/dismiss/{post_id}")
    def dismiss(post_id: str, show_dismissed: bool = Form(False)):
        store.dismiss(post_id)
        return RedirectResponse(f"/?show_dismissed={int(show_dismissed)}", status_code=303)

    return app
