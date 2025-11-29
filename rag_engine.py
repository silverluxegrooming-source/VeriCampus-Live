from PIL import Image
import pytesseract
from langchain_core.documents import Document # Import Document object
import os
import time
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
# Loaders
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone

load_dotenv()

# Check Keys
if not os.getenv("GROQ_API_KEY"): raise ValueError("GROQ_API_KEY missing")
if not os.getenv("HUGGINGFACEHUB_API_TOKEN"): raise ValueError("HUGGINGFACEHUB_API_TOKEN missing")
if not os.getenv("PINECONE_API_KEY"): raise ValueError("PINECONE_API_KEY missing")

print("Connecting to Cloud Systems...")

embeddings = HuggingFaceEndpointEmbeddings(
    model="sentence-transformers/all-MiniLM-L6-v2",
    huggingfacehub_api_token=os.getenv("HUGGINGFACEHUB_API_TOKEN")
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

def process_document(file_path, school_id):
    print(f"--- STARTING PROCESSING: {file_path} ---")
    
    docs = []
    try:
        # 1. LOAD
        if file_path.endswith(".pdf"):
            print("Detected PDF. Loading...")
            loader = PyPDFLoader(file_path)
            docs = loader.load()
        elif file_path.endswith(".docx"):
            print("Detected DOCX. Loading with Docx2txt...")
            loader = Docx2txtLoader(file_path)
            docs = loader.load()
        elif file_path.endswith(".txt"):
            print("Detected TXT. Loading...")
            loader = TextLoader(file_path)
            docs = loader.load()
        # --- NEW: IMAGE HANDLING ---
        elif file_path.lower().endswith(('.png', '.jpg', '.jpeg')):
            print("Detected Image. Running OCR...")
            # Extract text from image
            raw_text = pytesseract.image_to_string(Image.open(file_path))
            
            if not raw_text.strip():
                return "Error: No text found in this image. Is it clear enough?"
                
            # Convert to LangChain Document format
            docs = [Document(page_content=raw_text, metadata={"source": file_path})]
        # ---------------------------
        else:
            return "Error: Unsupported file type. Only PDF, DOCX, TXT PNG, JPG, and JPEG"
            
        if not docs:
            print("Error: Loader returned empty content.")
            return "Error: Document was empty."

        print(f"Successfully Loaded {len(docs)} pages/sections.")

        # 2. SPLIT
        print("Splitting text into chunks...")
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        all_splits = text_splitter.split_documents(docs)
        
        if not all_splits:
            print("Error: Splitter returned 0 chunks.")
            return "Error: Could not extract text chunks."

        print(f"Created {len(all_splits)} chunks. Uploading to Pinecone...")
        
        # 3. UPLOAD
        PineconeVectorStore.from_documents(
            documents=all_splits,
            embedding=embeddings,
            index_name=index_name,
            namespace=school_id.upper()
        )
        
        print("--- DONE! DATA SAVED ---")
        return f"Success! {len(all_splits)} chunks saved to {school_id} database."

    except Exception as e:
        print(f"CRITICAL ERROR in process_document: {e}")
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
    
    retriever = vector_store.as_retriever()
    
    template = """You are VeriCampus. Answer based on context.
    
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