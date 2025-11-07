import os
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import MarkdownHeaderTextSplitter
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
import logging

# ตั้งค่า Logging เพื่อดูรายละเอียดมากขึ้น
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- กำหนดชื่อโฟลเดอร์สำหรับเก็บ DB ---
CHROMA_PERSIST_DIRECTORY = "chroma_db"

# ตรวจสอบว่ามี API Key ใน environment
if "GEMINI_API_KEY" not in os.environ:
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        os.environ["GEMINI_API_KEY"] = api_key
    else:
        # Load environment variables from .env file if not already loaded
        from dotenv import load_dotenv
        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            os.environ["GEMINI_API_KEY"] = api_key

def setup_rag_chain(file_path: str):
    logger.info(f"Setting up RAG chain from MARKDOWN document: {file_path}")
    
    loader = TextLoader(file_path, encoding="utf-8")
    documents = loader.load()
    full_text = documents[0].page_content
    
    headers_to_split_on = [("#", "Header 1"), ("##", "Header 2"), ("###", "Header 3")]
    markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
    
    # แบ่งเนื้อหาตาม headers ก่อน
    splits = markdown_splitter.split_text(full_text)
    
    # ถ้าชิ้นส่วนใดยาวเกินไป ให้แบ่งย่อยอีกที
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
    )
    splits = text_splitter.split_documents(splits)
    
    embeddings_model = GoogleGenerativeAIEmbeddings(
        model="models/text-embedding-004",
        google_api_key=os.environ.get("GEMINI_API_KEY")
    )

    # --- ส่วนที่แก้ไข: สร้างหรือโหลด Vector Store ---
    if os.path.exists(CHROMA_PERSIST_DIRECTORY):
        logger.info(f"Loading existing vector store from: {CHROMA_PERSIST_DIRECTORY}")
        vectorstore = Chroma(
            persist_directory=CHROMA_PERSIST_DIRECTORY,
            embedding_function=embeddings_model
        )
    else:
        logger.info(f"Creating new vector store and persisting to: {CHROMA_PERSIST_DIRECTORY}")
        vectorstore = Chroma.from_documents(
            documents=splits, 
            embedding=embeddings_model,
            persist_directory=CHROMA_PERSIST_DIRECTORY
        )
        logger.info("Vector store created and persisted.")

    retriever = vectorstore.as_retriever(
        search_kwargs={
            'k': 16  # เพิ่มจำนวน chunks ที่จะดึงมาเพื่อให้ได้ข้อมูลมากขึ้น
        }
    )
    
    prompt_template = """คุณคือ "KMUTNB Buddy" ผู้ช่วย AI ที่เป็นมิตรและเชี่ยวชาญข้อมูลจากเอกสารของมหาวิทยาลัยเทคโนโลยีพระจอมเกล้าพระนครเหนือ
หน้าที่ของคุณคือตอบคำถามโดยใช้ข้อมูลจาก "Context" ที่ให้มาเป็นหลัก



**วิธีการตอบ:**
1.  อ่านและทำความเข้าใจข้อมูลทั้งหมดใน "Context" ที่เกี่ยวข้องกับคำถาม
2.  ใช้ความสามารถในการสรุปและเรียบเรียงภาษาของคุณเพื่อสร้างคำตอบที่ชัดเจนและเข้าใจง่าย
3.  คำตอบของคุณต้องอิงตามข้อเท็จจริงที่มีใน "Context" เท่านั้น ห้ามเสริมข้อมูลที่ไม่มีอยู่จริงเข้ามา
4.  หากไม่พบคำตอบใน "Context" เลย ให้ตอบว่า ขออภัยค่ะ KMUTNB Buddy ยังไม่สามารถตอบคำถามนี้ได้
5.  จะต้องไม่มี * เพื่อใช้เป็นหัวข้อหรือหัวข้อย่อยในคำตอบ
6.  ต้องเป็นคำตอบที่กระชับและเป็นมิตรกับผู้ใช้
"

**Context:**
{context}

**Question:** {input}

**Answer (เขียนคำตอบที่เป็นมิตรและสรุปจาก Context):**
"""
    prompt = ChatPromptTemplate.from_template(prompt_template)
    
    llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash-lite",  # ใช้โมเดลที่เสถียรกว่า
            google_api_key=os.environ.get("GEMINI_API_KEY"),
            temperature=0.3,
            max_output_tokens=4500,
            # max_output_tokens=2050,
            retry_on_throttle=True,
            max_retries=3
        )
    question_answer_chain = create_stuff_documents_chain(llm, prompt)
    rag_chain = create_retrieval_chain(retriever, question_answer_chain)
    
    logger.info("RAG chain setup complete.")
    
    # --- จุดที่แก้ไข Indentation ---
    return rag_chain

# --- สร้าง Chain ไว้ล่วงหน้าตอนเริ่มโปรแกรม ---
try:
    markdown_file_path = "kmutnbBuddy.md"
    RAG_CHAIN = setup_rag_chain(markdown_file_path)
except Exception as e:
    logger.error(f"FATAL: Error setting up RAG chain: {e}", exc_info=True)
    RAG_CHAIN = None

def answer_question(question: str) -> str:
    if RAG_CHAIN is None:
        return "ขออภัยค่ะ ระบบ RAG ยังไม่พร้อมใช้งานเนื่องจากเกิดข้อผิดพลาดในการเริ่มต้น"
        
    try:
        logger.info(f"Invoking RAG chain with question: '{question}'")
        response = RAG_CHAIN.invoke({"input": question})
        return response["answer"]
    except Exception as e:
        logger.error(f"Error invoking RAG chain: {e}", exc_info=True)
        return "เกิดข้อผิดพลาดในการประมวลผลคำถามค่ะ"