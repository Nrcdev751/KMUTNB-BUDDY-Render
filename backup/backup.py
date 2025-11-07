# rag_handler.py
import os
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_community.vectorstores import Chroma # แก้ไข import path ให้ถูกต้อง
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader # แก้ไข import path ให้ถูกต้อง
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
import logging

# ตั้งค่า Logging เพื่อดูรายละเอียดมากขึ้น
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ตรวจสอบว่ามี API Key ใน environment
if "GEMINI_API_KEY" not in os.environ:
    os.environ["GEMINI_API_KEY"] = os.getenv("GEMINI_API_KEY")

# --- ส่วนของการเตรียมข้อมูล (ทำครั้งเดียว) ---
def setup_rag_chain(file_path):
    logger.info(f"Setting up RAG chain from document: {r"E:\anaconda_project\BotNoi\kmutnbBuddy(tuned).pdf"}")
    # 1. โหลดเอกสาร PDF
    loader = PyPDFLoader(r"E:\anaconda_project\BotNoi\kmutnbBuddy(tuned).pdf")
    docs = loader.load()
    logger.info(f"Loaded {len(docs)} document pages.")

    # --- ส่วนที่เพิ่มเข้ามาเพื่อ DEBUG ---
    try:
        with open("extracted_content.txt", "w", encoding="utf-8") as f:
            full_text = "".join(doc.page_content for doc in docs)
            f.write(full_text)
        logger.info("Successfully saved extracted content to extracted_content.txt")
    except Exception as e:
        logger.error(f"Could not write to file: {e}")
    # --- จบส่วน DEBUG ---

    # 2. แบ่งเอกสารเป็น Chunks
    # --- แก้ไข 1: ปรับ Chunk size กลับมาที่ค่าที่เหมาะสม ---
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=7000, 
        chunk_overlap=1600
    )
    splits = text_splitter.split_documents(docs)
    logger.info(f"Split document into {len(splits)} chunks.")

    # 3. สร้าง Embeddings และเก็บใน ChromaDB
    embeddings_model = GoogleGenerativeAIEmbeddings(
        model="models/text-embedding-004",
        google_api_key=os.getenv("GEMINI_API_KEY")
    )
    vectorstore = Chroma.from_documents(documents=splits, embedding=embeddings_model)
    
    # สร้าง Retriever เพื่อใช้ในการค้นหา
    # --- แก้ไข 2: เพิ่ม k เพื่อดึงข้อมูลมามากขึ้น ---
    retriever = vectorstore.as_retriever(
        search_kwargs={'k': 8}
    )
    
    # 4. สร้าง Prompt Template
    prompt_template = """คุณคือ "KMUTNB Buddy" ผู้ช่วย AI ที่เป็นมิตรและเชี่ยวชาญข้อมูลจากเอกสารของมหาวิKมจพ.
หน้าที่ของคุณคือตอบคำถามโดยใช้ข้อมูลจาก "Context" ที่ให้มาเป็นหลัก

**วิธีการตอบ:**
1.  อ่านและทำความเข้าใจข้อมูลทั้งหมดใน "Context" ที่เกี่ยวข้องกับคำถาม
2.  ใช้ความสามารถในการสรุปและเรียบเรียงภาษาของคุณเพื่อสร้างคำตอบที่ชัดเจนและเข้าใจง่าย
3.  คำตอบของคุณต้องอิงตามข้อเท็จจริงที่มีใน "Context" เท่านั้น ห้ามเสริมข้อมูลที่ไม่มีอยู่จริงเข้ามา
4.  หากไม่พบคำตอบใน "Context" เลย ให้ตอบว่า "ขออภัยค่ะ ไม่พบข้อมูลที่เกี่ยวข้องในเอกสาร"

**Context:**
{context}

**Question:** {input}

**Answer (เขียนคำตอบที่เป็นมิตรและสรุปจาก Context):**
"""
    prompt = ChatPromptTemplate.from_template(prompt_template)
    
    # 5. สร้าง LLM Chain
    # --- แก้ไข 3: แก้ไขชื่อโมเดลให้ถูกต้อง ---
    llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash", 
            google_api_key=os.getenv("GEMINI_API_KEY"),
            temperature=0.7,
            max_output_tokens=4096 # เพิ่มเป็น 4096 tokens (ประมาณ 2-3 หน้า A4)
        )
    question_answer_chain = create_stuff_documents_chain(llm, prompt)
    
    # 6. สร้าง Retrieval Chain
    rag_chain = create_retrieval_chain(retriever, question_answer_chain)
    
    logger.info("RAG chain setup complete.")
    return rag_chain

# --- สร้าง Chain ไว้ล่วงหน้าตอนเริ่มโปรแกรม ---
try:
    # แนะนำให้ใช้ Relative Path ถ้าไฟล์อยู่ในโฟลเดอร์เดียวกัน
    RAG_CHAIN = setup_rag_chain("kmutnbBuddy(tuned).pdf")
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