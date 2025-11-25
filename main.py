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

# --- AUTH LOGIC (Updated for Mobile) ---
ADMIN_USER = "admin"
ADMIN_PASS = "password12345"

# --- ROUTES ---

# 1. LANDING PAGE
@app.get("/")
async def read_landing():
    return FileResponse('static/landing.html')

# 2. THE APP
@app.get("/app")
async def read_app():
    return FileResponse('static/index.html')

# 3. LOGIN PAGE (New)
@app.get("/login")
async def login_page():
    return FileResponse('static/login.html')

# 4. LOGIN ACTION (Handles the form post)
@app.post("/login")
async def login(response: Response, username: str = Form(...), password: str = Form(...)):
    if secrets.compare_digest(username, ADMIN_USER) and secrets.compare_digest(password, ADMIN_PASS):
        # Set a cookie that works on mobile
        response.set_cookie(key="admin_session", value="authenticated", httponly=True)
        return RedirectResponse(url="/admin", status_code=303)
    else:
        # If wrong, go back to login (You could add an error message logic here)
        return RedirectResponse(url="/login", status_code=303)

# 5. ADMIN PANEL (Protected by Cookie)
@app.get("/admin")
async def read_admin(request: Request):
    token = request.cookies.get("admin_session")
    if token != "authenticated":
        # If no cookie, redirect to login page
        return RedirectResponse(url="/login")
    return FileResponse('static/admin.html')

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