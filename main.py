import secrets
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, status, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
import shutil
import os
from rag_engine import process_document, ask_vericampus, add_realtime_update

app = FastAPI(title="VeriCampus Version 2.0")

# --- CONFIG ---
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- AUTH LOGIC ---
ADMIN_USER = "admin"
ADMIN_PASS = "password12345"

# --- ROUTES ---

@app.get("/")
async def read_landing():
    return FileResponse('static/landing.html')

@app.get("/app")
async def read_app():
    return FileResponse('static/index.html')

@app.get("/login")
async def login_page():
    return FileResponse('static/login.html')

# --- LOGIN ACTION (FIXED FOR MOBILE) ---
@app.post("/login")
async def login(response: Response, username: str = Form(...), password: str = Form(...)):
    if secrets.compare_digest(username, ADMIN_USER) and secrets.compare_digest(password, ADMIN_PASS):
        # 1. Set Cookie (Best practice for web)
        response.set_cookie(key="admin_session", value="authenticated", httponly=True)
        
        # 2. Redirect with URL Parameter (The "Mobile Fix")
        # This forces the app to recognize you are logged in, even if it drops the cookie.
        return RedirectResponse(url="/admin?auth=success", status_code=303)
    else:
        # Failed login
        return RedirectResponse(url="/login?error=invalid", status_code=303)

# --- ADMIN PANEL (FIXED FOR MOBILE) ---
@app.get("/admin")
async def read_admin(request: Request):
    # Check 1: Is the Cookie there?
    cookie_token = request.cookies.get("admin_session")
    
    # Check 2: Is the URL Parameter there? (Fallback for Android App)
    url_token = request.query_params.get("auth")

    if cookie_token == "authenticated" or url_token == "success":
        return FileResponse('static/admin.html')
    
    # If neither found, kick them out
    return RedirectResponse(url="/login")

# --- API ENDPOINTS (Unchanged) ---
@app.post("/upload-handbook")
async def upload_handbook(file: UploadFile = File(...), school_id: str = Form(...)):
    file_location = f"temp_{file.filename}"
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    try:
        result = process_document(file_location, school_id)
    except Exception as e:
        result = f"Server Error: {str(e)}"
    if os.path.exists(file_location): os.remove(file_location)
    return {"message": result}

@app.post("/chat")
async def chat(question: str = Form(...), school_id: str = Form(...)):
    answer = ask_vericampus(question, school_id)
    return {"answer": answer}

@app.post("/broadcast-update")
async def broadcast(update: str = Form(...), author: str = Form(...)):
    result = add_realtime_update(update, author)
    return {"message": result}