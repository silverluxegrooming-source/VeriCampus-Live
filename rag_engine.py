import os
import time
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
# New: Pinecone Import
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone

load_dotenv()

if not os.getenv("GROQ_API_KEY"): raise ValueError("GROQ_API_KEY missing")
if not os.getenv("HUGGINGFACEHUB_API_TOKEN"): raise ValueError("HUGGINGFACEHUB_API_TOKEN missing")
if not os.getenv("PINECONE_API_KEY"): raise ValueError("PINECONE_API_KEY missing")

print("Connecting to Cloud Systems...")

# 1. READER (Embeddings)
embeddings = HuggingFaceEndpointEmbeddings(
    model="sentence-transformers/all-MiniLM-L6-v2",
    huggingfacehub_api_token=os.getenv("HUGGINGFACEHUB_API_TOKEN")
)

# 2. DATABASE (Pinecone - Permanent Cloud Storage)
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index_name = "vericampus-db" 

# 3. TALKER (Groq)
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.3,
    max_tokens=1024,
    api_key=os.getenv("GROQ_API_KEY")
)

real_time_updates = [] 

def process_pdf(file_path, school_id):
    print(f"Processing PDF for School: {school_id}...")
    loader = PyPDFLoader(file_path)
    docs = loader.load()
    
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    all_splits = text_splitter.split_documents(docs)
    
    print(f"Uploading {len(all_splits)} chunks to Pinecone Cloud...")
    
    # Save to Pinecone. Namespace keeps schools separate.
    # This data persists even if your laptop/server dies.
    PineconeVectorStore.from_documents(
        documents=all_splits, 
        embedding=embeddings, 
        index_name=index_name,
        namespace=school_id.upper()
    )
            
    print("Done! Data Saved Permanently.")
    return f"Success! Saved to {school_id} cloud database."

def add_realtime_update(update_text, author):
    real_time_updates.append(f"URGENT: {author} says: {update_text}")
    return "Update broadcasted."

def ask_vericampus(question, school_id):
    # Connect to the specific School's Cloud Memory
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
    
    def format_docs(docs): return "\n\n".join([d.page_content for d in docs])
    
    chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough(), "real_time_info": lambda x: rt_context}
        | prompt | llm | StrOutputParser()
    )
    return chain.invoke(question)