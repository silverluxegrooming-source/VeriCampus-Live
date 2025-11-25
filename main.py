import secrets
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import shutil
import os
from rag_engine import process_document, ask_vericampus, add_realtime_update

app = FastAPI(title="VeriCampus Version 2.0")

# --- SECURITY ---
security = HTTPBasic()
def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = "admin"
    correct_password = "password12345" 
    is_correct_username = secrets.compare_digest(credentials.username, correct_username)
    is_correct_password = secrets.compare_digest(credentials.password, correct_password)
    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# --- ROUTES ---

# 1. LANDING PAGE (Marketing Website)
@app.get("/")
async def read_landing():
    return FileResponse('static/landing.html')

# 2. THE APP (Student Chat Interface)
@app.get("/app")
async def read_app():
    return FileResponse('static/index.html')

# 3. ADMIN PANEL
@app.get("/admin")
async def read_admin(username: str = Depends(get_current_username)):
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