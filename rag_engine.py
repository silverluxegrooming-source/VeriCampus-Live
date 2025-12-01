from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
from langchain_core.documents import Document 
import os
import time
import platform
from dotenv import load_dotenv
from langchain_groq import ChatGroq
# --- SWITCHED BACK TO CLOUD ENDPOINT (SAVES RAM) ---
from langchain_huggingface import HuggingFaceEndpointEmbeddings 
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

load_dotenv()

# Check Keys
if not os.getenv("GROQ_API_KEY"): raise ValueError("GROQ_API_KEY missing")
if not os.getenv("HUGGINGFACEHUB_API_TOKEN"): raise ValueError("HUGGINGFACEHUB_API_TOKEN missing")
if not os.getenv("PINECONE_API_KEY"): raise ValueError("PINECONE_API_KEY missing")

print("Connecting to Cloud Systems...")

# --- LIGHTWEIGHT CLOUD EMBEDDINGS ---
embeddings = HuggingFaceEndpointEmbeddings(
    model="sentence-transformers/all-MiniLM-L6-v2",
    huggingfacehub_api_token=os.getenv("HUGGINGFACEHUB_API_TOKEN"),
    timeout=60 # Wait longer before failing
)

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index_name = "vericampus-db" 

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.3,
    max_tokens=1024,
    api_key=os.getenv("GROQ_API_KEY")
)

real_time_updates = [] 

def enhance_image_for_ocr(image_path):
    try:
        img = Image.open(image_path)
        img = img.convert('L') 
        width, height = img.size
        new_size = (width * 3, height * 3) 
        img = img.resize(new_size, Image.Resampling.LANCZOS)
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0) 
        img = img.filter(ImageFilter.SHARPEN)
        return img
    except Exception as e:
        print(f"Enhance failed: {e}")
        return Image.open(image_path)

# --- RETRY LOGIC WRAPPER ---
def safe_embed_documents(documents, school_id, retries=3):
    """
    Tries to upload to Pinecone. If HuggingFace is busy (504), 
    it waits 5 seconds and tries again.
    """
    for attempt in range(retries):
        try:
            PineconeVectorStore.from_documents(
                documents=documents,
                embedding=embeddings,
                index_name=index_name,
                namespace=school_id.upper()
            )
            return True # Success
        except Exception as e:
            print(f"⚠️ Upload Attempt {attempt+1} failed: {e}")
            if attempt < retries - 1:
                print("Waiting 5 seconds before retrying...")
                time.sleep(5)
            else:
                return False # Failed after all retries

def process_document(file_path, school_id):
    print(f"--- STARTING PROCESSING: {file_path} ---")
    docs = []
    try:
        if file_path.endswith(".pdf"):
            loader = PyPDFLoader(file_path)
            docs = loader.load()
        elif file_path.endswith(".docx"):
            loader = Docx2txtLoader(file_path)
            docs = loader.load()
        elif file_path.endswith(".txt"):
            loader = TextLoader(file_path)
            docs = loader.load()
        elif file_path.lower().endswith(('.png', '.jpg', '.jpeg')):
            print("Detected Image. Running OCR...")
            clean_image = enhance_image_for_ocr(file_path)
            raw_text = pytesseract.image_to_string(clean_image)
            print(f"--- EXTRACTED: ---\n{raw_text[:500]}...\n------------------")
            
            if len(raw_text.strip()) < 5:
                return "Error: Image unclear or empty."
            docs = [Document(page_content=raw_text, metadata={"source": file_path})]
        else:
            return "Error: Unsupported file type."
            
        if not docs: return "Error: Document empty."

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        all_splits = text_splitter.split_documents(docs)
        
        print(f"Uploading {len(all_splits)} chunks...")
        
        # USE THE NEW SAFE UPLOAD
        success = safe_embed_documents(all_splits, school_id)
        
        if success:
            return f"Success! Knowledge Base Updated for {school_id}."
        else:
            return "Error: Cloud Server busy. Please try uploading again in 1 minute."

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        return f"Processing Error: {str(e)}"

def add_realtime_update(update_text, author):
    real_time_updates.append(f"URGENT: {author} says: {update_text}")
    return "Update broadcasted."

def ask_vericampus(question, school_id):
    vector_store = PineconeVectorStore(
        index_name=index_name,
        embedding=embeddings,
        namespace=school_id.upper()
    )
    
    # Retry logic for retrieval as well
    try:
        retriever = vector_store.as_retriever(search_kwargs={"k": 4})
        
        template = """You are VeriCampus AI, an intelligent academic tutor.
        Mission:
        1. Answer based strictly on Context.
        2. Solve exam questions step-by-step.
        
        Context: {context}
        Updates: {real_time_info}
        Question: {question}
        Answer:"""
        
        prompt = ChatPromptTemplate.from_template(template)
        rt_context = "\n".join(real_time_updates) if real_time_updates else "None"
        
        chain = (
            {"context": retriever, "question": RunnablePassthrough(), "real_time_info": lambda x: rt_context}
            | prompt | llm | StrOutputParser()
        )
        return chain.invoke(question)
    except Exception as e:
        return "Network busy. Please ask again."