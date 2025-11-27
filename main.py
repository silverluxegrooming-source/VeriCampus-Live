import secrets
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, status, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
import shutil
import os
from rag_engine import process_document, ask_vericampus, add_realtime_update

# --- NEW FIREBASE IMPORTS ---
import firebase_admin
from firebase_admin import credentials, messaging

app = FastAPI(title="VeriCampus Version 2.0")

# --- FIREBASE SETUP ---
# This checks if firebase is already running so it doesn't crash on reload
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate("firebase_key.json")
        firebase_admin.initialize_app(cred)
        print("Firebase Initialized Successfully")
    except Exception as e:
        print(f"Firebase Init Error: {e}")

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

@app.post("/login")
async def login(response: Response, username: str = Form(...), password: str = Form(...)):
    if secrets.compare_digest(username, ADMIN_USER) and secrets.compare_digest(password, ADMIN_PASS):
        response.set_cookie(key="admin_session", value="authenticated", httponly=True)
        return RedirectResponse(url="/admin?auth=success", status_code=303)
    else:
        return RedirectResponse(url="/login?error=invalid", status_code=303)

@app.get("/admin")
async def read_admin(request: Request):
    cookie_token = request.cookies.get("admin_session")
    url_token = request.query_params.get("auth")
    if cookie_token == "authenticated" or url_token == "success":
        return FileResponse('static/admin.html')
    return RedirectResponse(url="/login")

# --- API ENDPOINTS ---
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

# --- UPDATED BROADCAST ENDPOINT (WITH NOTIFICATIONS) ---
@app.post("/broadcast-update")
async def broadcast(update: str = Form(...), author: str = Form(...), school_id: str = Form(...)):
    # 1. Add to chat history logic
    result = add_realtime_update(update, author)
    
    # 2. Send Push Notification
    try:
        topic = school_id.upper() # Ensure this matches what the app subscribed to
        
        # Construct message
        message = messaging.Message(
            notification=messaging.Notification(
                title=f"📢 Update from {author}",
                body=update,
            ),
            topic=topic,
        )
        
        # Send
        response = messaging.send(message)
        print(f"Successfully sent notification to {topic}: {response}")
        return {"message": "Broadcast sent and Notification Pushed!"}
        
    except Exception as e:
        print(f"Notification Error: {e}")
        return {"message": "Broadcast saved, but Notification failed."}