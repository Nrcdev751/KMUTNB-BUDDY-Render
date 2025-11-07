from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    ImageMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

import google.generativeai as genai
import os
from rag_handler import answer_question # ต้องมั่นใจว่า answer_question สามารถใช้ 'user_message' เป็น input ได้
from contact_data import contact_info_db
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

# LINE Bot Config
configuration = Configuration(access_token='kjoDJiMr9t76qcUAy8BkYWVo1+tpP/su3tYLmvUrI6R67nLGarVh8yOTWJJDJzL6L7fJKO/FCL6SKkSoCYWUoQAiPyFeLEklsS/31cEWZZ3lUW9TMD4ZwcqnI+p4+mV3u/Zy4KNR7yyOoBDdtW1/fAdB04t89/1O/w1cDnyilFU=')
handler = WebhookHandler('fcee06db289c6014ee1d3dd45fdf96b8')

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 2048,
    "response_mime_type": "text/plain",
}

@app.get('/hello')
def hello_world():
    return {"hello" : "world"}

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.info("Invalid signature.")
        abort(400)

    return 'OK'

# Dictionary สำหรับเก็บ chat session ของ Gemini สำหรับผู้ใช้แต่ละคน เพื่อรักษาสถานะการสนทนา
user_gemini_sessions = {}

def get_or_create_chat_session(user_id):
    """ดึงหรือสร้าง Gemini chat session สำหรับผู้ใช้ที่ระบุ"""
    if user_id not in user_gemini_sessions:
        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash-lite", # ใช้โมเดลที่ต้องการ
            generation_config=generation_config,
        )
        user_gemini_sessions[user_id] = model.start_chat(history=[]) # เริ่ม chat session ใหม่พร้อมประวัติว่างเปล่า
    return user_gemini_sessions[user_id]


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text
    final_bot_text_response = ""
    messages_to_reply = []
    user_message_lower = user_message.lower()
    messages_to_reply = []
    final_bot_text_response = "" # ตัวแปรสำหรับเก็บข้อความตอบกลับสุดท้ายของบอท

    # ดึงหรือสร้าง Gemini chat session สำหรับผู้ใช้คนนี้
    # เราจะใช้ session นี้เพื่อจัดการประวัติการสนทนา
    gemini_chat_session = get_or_create_chat_session(user_id)

    # *** ขั้นตอนสำคัญสำหรับความต่อเนื่อง: เพิ่มข้อความของผู้ใช้เข้าสู่ประวัติของ Gemini ทันที ***
    # การเรียก send_message() ในครั้งแรกจะเพิ่มข้อความของผู้ใช้เข้าสู่ history
    # และเราจะได้ response แรกที่ Gemini ประมวลผลโดยมีบริบทจากประวัติก่อนหน้า
    # อย่างไรก็ตาม เราจะใช้ response นี้ก็ต่อเมื่อ RAG ไม่ได้ให้คำตอบ
    try:
        # ส่งข้อความผู้ใช้เข้าสู่ Gemini session เพื่อให้ Gemini อัปเดตประวัติของมัน
        # และรับคำตอบเบื้องต้นจาก Gemini (ซึ่งอาจจะถูกใช้หรือไม่ใช้ก็ได้ ขึ้นอยู่กับเงื่อนไขต่อไป)
        gemini_initial_response = gemini_chat_session.send_message(user_message)
        gemini_contextual_text = gemini_initial_response.text
        app.logger.info(f"Gemini initial response for '{user_message}': {gemini_contextual_text[:50]}...")
    except Exception as e:
        app.logger.error(f"Error getting initial Gemini response for user {user_id}: {e}")
        gemini_contextual_text = "" # ให้เป็นสตริงว่างเปล่าหากมีข้อผิดพลาด

    # 1. ตรวจสอบคำทักทาย (Rule-based)
    if user_message in ['สวัสดี', 'นี่ใคร'] or user_message.startswith('สวัสดี'):
        final_bot_text_response = "สวัสดีค่ะ KMUTNB Buddy ยินดีให้บริการ"
        messages_to_reply.append(TextMessage(text=final_bot_text_response))

    elif any(kw in user_message_lower for kw in ['เบอร์โทร', 'โทรศัพท์', 'ติดต่อ', 'อีเมล', 'email', 'ช่องทางติดต่อ', 'เบอร์', 'อาจารย์', 'บุคลากร']):
        
        response_parts = []
        found_match = False
        
        # --- Stage 1: ตรวจสอบว่าผู้ใช้ถามถึงรายชื่อบุคลากรทั้งหมดในคณะ/ภาควิชาหรือไม่ ---
        # Keywords ที่บ่งบอกถึงการขอรายชื่อทั้งหมด
        list_keywords = ['รายชื่อ', 'ทั้งหมด', 'ทุกคน', 'บุคลากรของ', 'อาจารย์ใน']
        
        # ค้นหาคณะ/ภาควิชาที่ผู้ใช้อ้างถึง
        target_dept_name = None
        for dept_name, dept_data in contact_info_db.items():
            if any(k.lower() in user_message_lower for k in dept_data["keywords"]):
                target_dept_name = dept_name
                break

        if target_dept_name and any(lk in user_message_lower for lk in list_keywords):
            # ผู้ใช้ต้องการรายชื่อบุคลากรทั้งหมดในคณะนี้
            dept_data = contact_info_db[target_dept_name]
            response_parts.append(f"รายชื่อบุคลากรใน {target_dept_name}:")
            
            if dept_data.get("บุคลากร"):
                for person_name, person_data in dept_data["บุคลากร"].items():
                    contact_details = []
                    
                    phone_info = person_data.get("เบอร์โทร")
                    email_info = person_data.get("อีเมล")

                    if phone_info:
                        contact_details.append(f"โทร: {phone_info}")
                    if email_info:
                        contact_details.append(f"อีเมล: {email_info}")
                    
                    details_str = ""
                    if contact_details:
                        details_str = f" ({', '.join(contact_details)})"
                    
                    response_parts.append(f"- {person_data['ตำแหน่ง']} {person_name}{details_str}")
                found_match = True
            else:
                response_parts.append("ไม่พบข้อมูลบุคลากรในคณะนี้ค่ะ")
        
        # --- Stage 2: หากไม่ได้ถามถึงรายชื่อทั้งหมด, ลองหาข้อมูลบุคลากรเฉพาะเจาะจง ---
        if not found_match:
            for dept_name, dept_data in contact_info_db.items():
                for person_name, person_data in dept_data.get("บุคลากร", {}).items():
                    # ตรวจสอบชื่อเต็ม หรือส่วนหนึ่งของชื่อ, หรือตำแหน่ง
                    # สามารถเพิ่มความซับซ้อนในการจับคู่ชื่อได้ เช่น ใช้ fuzzy matching
                    person_keywords = [pn.lower() for pn in person_name.split()] + [pos.lower() for pos in person_data['ตำแหน่ง'].split()]
                    
                    if any(pk in user_message_lower for pk in person_keywords) and \
                       not any(lk in user_message_lower for lk in list_keywords): # ต้องแน่ใจว่าไม่ได้ถามถึง "รายชื่อทั้งหมด"
                        response_parts.append(f"ข้อมูลติดต่อสำหรับ {person_data['ตำแหน่ง']} {person_name} (สังกัด{dept_name}):")
                        
                        contact_details = []
                        phone_info = person_data.get("เบอร์โทร")
                        email_info = person_data.get("อีเมล")

                        if phone_info:
                            contact_details.append(f"โทร: {phone_info}")
                        if email_info:
                            contact_details.append(f"อีเมล: {email_info}")
                        
                        if contact_details:
                            response_parts.append(f"{' '.join(contact_details)}")
                        else:
                            response_parts.append("ไม่พบข้อมูลการติดต่อที่ระบุค่ะ")
                        
                        found_match = True
                        break # เจอข้อมูลบุคลากรแล้ว ออกจากลูปบุคลากร
                if found_match:
                    break # เจอข้อมูลบุคลากรในคณะแล้ว ออกจากลูปคณะ

        # --- Stage 3: หากยังไม่เจอข้อมูลบุคลากรเฉพาะเจาะจงหรือรายชื่อทั้งหมด ลองหาข้อมูลคณะทั่วไป ---
        if not found_match:
            for dept_name, dept_data in contact_info_db.items():
                if any(k.lower() in user_message_lower for k in dept_data["keywords"]):
                    response_parts.append(f"ข้อมูลติดต่อสำหรับ {dept_name}:")
                    if dept_data.get("เบอร์กลาง"):
                        response_parts.append(f"  เบอร์โทรศัพท์ส่วนกลาง: {dept_data['เบอร์กลาง']}")
                    else:
                        response_parts.append("  ไม่พบเบอร์โทรศัพท์ส่วนกลางที่ระบุค่ะ")
                    response_parts.append(f"หากต้องการข้อมูลของบุคลากรเฉพาะเจาะจง โปรดระบุชื่อหรือตำแหน่งให้ชัดเจนค่ะ หรือดูรายละเอียดเพิ่มเติมในเอกสาร '1.2 ข้อมูลการติดต่ออาจารย์และเจ้าหน้าที่คณะต่างๆ'")
                    found_match = True
                    break

        # --- สรุปคำตอบสุดท้ายสำหรับคำถามติดต่อ ---
        if found_match:
            final_bot_text_response = "\n".join(response_parts)
        else:
            final_bot_text_response = (
                "ขออภัยค่ะ ฉันไม่พบข้อมูลติดต่อสำหรับสิ่งที่คุณกำลังมองหา\n\n"
                "คุณสามารถลองระบุชื่อบุคคล ตำแหน่ง หรือชื่อคณะ/ภาควิชาให้ชัดเจนยิ่งขึ้นได้ไหมคะ "
                "เช่น 'เบอร์โทรอาจารย์ยุพาภรณ์', 'รายชื่ออาจารย์คณะวิทยาศาสตร์ประยุกต์' หรือ 'ติดต่อคณะศิลปศาสตร์ประยุกต์' "
                "หรือดูในเอกสาร '1.2 ข้อมูลการติดต่ออาจารย์และเจ้าหน้าที่คณะต่างๆ' ค่ะ"
            )
            messages_to_reply.append(TextMessage(text=final_bot_text_response))
            return messages_to_reply 

    # 2. หากเจอคีย์เวิร์ด "การแต่งกาย"
    elif "การแต่งกาย" in user_message:
        # พยายามหาคำตอบจาก RAG ก่อน
        ai_response_text = answer_question(user_message) 
        
        # หาก RAG ไม่มีข้อมูล ให้ใช้คำตอบจาก Gemini ที่ได้ประมวลผลไปแล้ว
        if not ai_response_text or ai_response_text.strip() == "":
            app.logger.info(f"RAG did not find an answer for '{user_message}', falling back to Gemini with continuity.")
            final_bot_text_response = gemini_contextual_text if gemini_contextual_text else "ขออภัยค่ะ ฉันไม่พบข้อมูลการแต่งกายที่เฉพาะเจาะจง"
        else:
            final_bot_text_response = ai_response_text # ใช้คำตอบจาก RAG
        
        # หากทั้ง RAG และ Gemini ไม่มีคำตอบ (หรือมีข้อผิดพลาด)
        if not final_bot_text_response or final_bot_text_response.strip() == "":
            final_bot_text_response = "ขออภัยค่ะ ฉันไม่พบข้อมูลการแต่งกายที่เฉพาะเจาะจง แต่เรามีรูปภาพแนวทางการแต่งกายมาให้พิจารณาค่ะ"
        
        messages_to_reply.append(TextMessage(text=final_bot_text_response))

        # เพิ่มชุดรูปภาพการแต่งกาย
        image_urls = [
            "https://i.postimg.cc/pL5wW60S/492254752-1212904400841195-3294721946119439077-n.jpg",
            # เพิ่ม URL รูปภาพการแต่งกายอื่นๆ ที่นี่
        ]
        for url in image_urls:
            messages_to_reply.append(ImageMessage(original_content_url=url, preview_image_url=url))
    
    # 3. หากเจอคีย์เวิร์ด "แผนที่"
    elif "แผนที่" in user_message:
        # พยายามหาคำตอบจาก RAG ก่อน
        ai_response_text = answer_question(user_message)
        
        # หาก RAG ไม่มีข้อมูล ให้ใช้คำตอบจาก Gemini ที่ได้ประมวลผลไปแล้ว
        if not ai_response_text or ai_response_text.strip() == "":
            app.logger.info(f"RAG did not find an answer for '{user_message}', falling back to Gemini with continuity.")
            final_bot_text_response = gemini_contextual_text if gemini_contextual_text else "นี่คือแผนที่มหาวิทยาลัยเทคโนโลยีพระจอมเกล้าพระนครเหนือค่ะ"
        else:
            final_bot_text_response = ai_response_text
        
        if not final_bot_text_response or final_bot_text_response.strip() == "":
            final_bot_text_response = "นี่คือแผนที่มหาวิทยาลัยเทคโนโลยีพระจอมเกล้าพระนครเหนือค่ะ เพื่อความสะดวกในการเดินทาง"
        
        messages_to_reply.append(TextMessage(text=final_bot_text_response))

        # เพิ่มชุดรูปภาพแผนที่
        map_image_urls = [
         "https://i.postimg.cc/mrjfJFX0/481452366-3893729620865001-8488278701718064335-n.jpg", # แผนที่หลักของ มจพ.

        ]
        for url in map_image_urls:
            messages_to_reply.append(ImageMessage(original_content_url=url, preview_image_url=url))
    
    # 4. สำหรับข้อความอื่นๆ ทั้งหมด (General questions)
    else:
        # พยายามหาคำตอบจาก RAG ก่อน
        ai_response_text = answer_question(user_message)
        
        # หาก RAG ไม่มีข้อมูล ให้ใช้คำตอบจาก Gemini ที่ได้ประมวลผลไปแล้ว
        if not ai_response_text or ai_response_text.strip() == "":
            app.logger.info(f"RAG did not find an answer for '{user_message}', falling back to Gemini with continuity.")
            final_bot_text_response = gemini_contextual_text if gemini_contextual_text else "ขออภัยค่ะ ฉันไม่เข้าใจคำถามของคุณ โปรดลองถามในรูปแบบอื่นนะคะ"
        else:
            final_bot_text_response = ai_response_text
        
        if not final_bot_text_response or final_bot_text_response.strip() == "":
            final_bot_text_response = "ขออภัยค่ะ ฉันไม่เข้าใจคำถามของคุณ โปรดลองถามในรูปแบบอื่นนะคะ"

        messages_to_reply.append(TextMessage(text=final_bot_text_response))

    # *** ขั้นตอนสำคัญสำหรับความต่อเนื่อง: เพิ่มข้อความตอบกลับของบอท (Text) เข้าไปในประวัติของ Gemini ***
    # เพื่อให้ Gemini ทราบว่าบอทตอบอะไรไปแล้ว แม้ว่าคำตอบนั้นจะมาจาก RAG หรือกฎ
    if final_bot_text_response and final_bot_text_response.strip() != "":
        try:
            # เพิ่มการตอบกลับของบอทเข้าไปใน history ของ Gemini
            gemini_chat_session.history.append(genai.types.contents.Content(parts=[final_bot_text_response], role="model"))
            app.logger.info(f"Added bot response to Gemini history for user {user_id}: {final_bot_text_response[:50]}...")
        except Exception as e:
            app.logger.error(f"Failed to manually add bot response to Gemini history for user {user_id}: {e}")

    # ส่งข้อความและ/หรือรูปภาพตอบกลับไปยัง LINE
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=messages_to_reply
            )
        )

# ฟังก์ชัน chat_with_gemini ไม่จำเป็นต้องเรียกใช้โดยตรงใน handle_message อีกต่อไป
# เพราะเราได้รวม logic การส่งข้อความเข้าสู่ session ของ Gemini ไว้ใน handle_message แล้ว
# อย่างไรก็ตาม หากคุณต้องการใช้ฟังก์ชันนี้สำหรับงานอื่น ๆ ก็ยังคงเก็บไว้ได้
# def chat_with_gemini(user_id, user_message):
#     chat_session = get_or_create_chat_session(user_id)
#     response = chat_session.send_message(user_message) # เพิ่มข้อความผู้ใช้และสร้างคำตอบ
#     print('Gemini Response:', response.text)
#     return response.text

if __name__ == "__main__":
    app.run(port=5000)