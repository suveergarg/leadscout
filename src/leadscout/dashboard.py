from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from leadscout.store import Store

_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def create_app(store: Store, subreddits: list[str] | None = None) -> FastAPI:
    """subreddits is the currently-configured monitor list (settings.subreddits) - used only
    to show monitored-but-not-yet-scanned subreddits on the /subreddits tab with a 0 count,
    rather than that tab silently omitting them."""
    monitored = subreddits or []
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

    @app.post("/responded/{post_id}")
    def responded(post_id: str, show_dismissed: bool = Form(False)):
        store.mark_responded(post_id)
        return RedirectResponse(f"/?show_dismissed={int(show_dismissed)}", status_code=303)

    @app.get("/subreddits")
    def subreddits_view(request: Request):
        stats = store.subreddit_stats()
        subs = set(monitored) | set(stats)
        rows = [
            {
                "subreddit": sub,
                "scanned": stats.get(sub, {}).get("scanned", 0),
                "leads": stats.get(sub, {}).get("leads", 0),
                "monitored": sub in monitored,
            }
            for sub in subs
        ]
        rows.sort(key=lambda r: (-r["scanned"], r["subreddit"].lower()))
        return _TEMPLATES.TemplateResponse(request, "subreddits.html", {"rows": rows})

    return app
