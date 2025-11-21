from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import shutil
import os
# Import the multi-tenant functions from your rag_engine
from rag_engine import process_pdf, ask_vericampus, add_realtime_update

app = FastAPI(title="VeriCampus Production API")

# 1. Security
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Frontend Serving
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- PAGES ---
@app.get("/")
async def read_index():
    return FileResponse('static/index.html')

@app.get("/admin")
async def read_admin():
    return FileResponse('static/admin.html')

# --- API ENDPOINTS (Updated for School ID) ---

@app.post("/upload-handbook")
async def upload_handbook(
    file: UploadFile = File(...), 
    school_id: str = Form(...)  # <-- CRITICAL: Receives School ID
):
    file_location = f"temp_{file.filename}"
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Send file AND school_id to the brain
    result = process_pdf(file_location, school_id)
    
    os.remove(file_location)
    return {"message": result}

@app.post("/chat")
async def chat(
    question: str = Form(...),
    school_id: str = Form(...) # <-- CRITICAL: Receives School ID
):
    # Ask the specific school's brain
    answer = ask_vericampus(question, school_id)
    return {"answer": answer}

@app.post("/broadcast-update")
async def broadcast(update: str = Form(...), author: str = Form(...)):
    result = add_realtime_update(update, author)
    return {"message": result}