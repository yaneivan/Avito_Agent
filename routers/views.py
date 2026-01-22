from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["views"])
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@router.get("/deep_research", response_class=HTMLResponse)
async def deep_research_view(request: Request):
    return templates.TemplateResponse("deep_research.html", {"request": request})

@router.get("/chat_history", response_class=HTMLResponse)
async def chat_history_view(request: Request):
    return templates.TemplateResponse("chat_history.html", {"request": request})