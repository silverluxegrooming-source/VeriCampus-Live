import os
import time
import shutil
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

# --- CONFIGURATION ---
DB_FOLDER = "school_data"
if not os.path.exists(DB_FOLDER):
    os.makedirs(DB_FOLDER)

# 1. Setup AI Models
embeddings = HuggingFaceEndpointEmbeddings(
    model="sentence-transformers/all-MiniLM-L6-v2",
    huggingfacehub_api_token=os.getenv("HUGGINGFACEHUB_API_TOKEN")
)

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.3,
    max_tokens=1024,
    api_key=os.getenv("GROQ_API_KEY")
)

# Global Storage
vector_store_cache = {}
real_time_updates = [] # <--- Added this back!

# --- CORE FUNCTIONS ---

def get_school_path(school_id):
    """Returns the folder path for a specific school's data"""
    clean_id = school_id.strip().lower().replace(" ", "_")
    return os.path.join(DB_FOLDER, clean_id)

def load_school_brain(school_id):
    """Loads a specific school's brain from disk into memory"""
    path = get_school_path(school_id)
    
    # If already in memory, return it
    if school_id in vector_store_cache:
        return vector_store_cache[school_id]
    
    # If on disk, load it
    if os.path.exists(path):
        print(f"Loading brain for {school_id} from disk...")
        try:
            store = FAISS.load_local(path, embeddings, allow_dangerous_deserialization=True)
            vector_store_cache[school_id] = store
            return store
        except Exception as e:
            print(f"Error loading brain: {e}")
            return None
            
    return None

def process_pdf(file_path, school_id):
    """Reads PDF and saves it into the SPECIFIC school's locker"""
    print(f"Processing PDF for School: {school_id}...")
    
    loader = PyPDFLoader(file_path)
    docs = loader.load()
    
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    all_splits = text_splitter.split_documents(docs)
    
    # Process in batches
    batch_size = 5
    vector_store = load_school_brain(school_id)
    
    for i in range(0, len(all_splits), batch_size):
        batch = all_splits[i:i+batch_size]
        print(f"Processing batch {i}...")
        try:
            if vector_store is None:
                vector_store = FAISS.from_documents(batch, embeddings)
            else:
                vector_store.add_documents(batch)
            time.sleep(1)
        except Exception as e:
            return f"Failed at batch {i}: {e}"
            
    # SAVE TO DISK
    save_path = get_school_path(school_id)
    vector_store.save_local(save_path)
    vector_store_cache[school_id] = vector_store
    
    return f"Success! Saved to {school_id} database."

# <--- Added this function back!
def add_realtime_update(update_text, author):
    real_time_updates.append(f"URGENT UPDATE from {author}: {update_text}")
    return "Update broadcasted to all schools."

def ask_vericampus(question, school_id):
    """Asks a question to a SPECIFIC school's brain"""
    vector_store = load_school_brain(school_id)
    
    if not vector_store:
        return "No data found for this School ID. Please upload a handbook first."

    retriever = vector_store.as_retriever()
    
    # Updated template to include Real-Time Info again
    template = """You are VeriCampus, the AI Assistant for {school_id}. 
    Answer the student's question based on the context below.
    
    Context: {context}
    
    Real-Time Updates: {real_time_info}
    
    Question: {question}
    
    Answer:"""
    
    prompt = ChatPromptTemplate.from_template(template)
    
    rt_context = "\n".join(real_time_updates) if real_time_updates else "No active updates."
    
    chain = (
        {"context": retriever, "question": RunnablePassthrough(), "school_id": lambda x: school_id, "real_time_info": lambda x: rt_context}
        | prompt | llm | StrOutputParser()
    )
    return chain.invoke(question)