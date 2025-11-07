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
from rag_handler import answer_question
from contact_data import contact_info_db
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

configuration = Configuration(access_token=os.getenv('LINE_CHANNEL_ACCESS_TOKEN', 'kjoDJiMr9t76qcUAy8BkYWVo1+tpP/su3tYLmvUrI6R67nLGarVh8yOTWJJDJzL6L7fJKO/FCL6SKkSoCYWUoQAiPyFeLEklsS/31cEWZZ3lUW9TMD4ZwcqnI+p4+mV3u/Zy4KNR7yyOoBDdtW1/fAdB04t89/1O/w1cDnyilFU='))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET', 'fcee06db289c6014ee1d3dd45fdf96b8'))

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

user_gemini_sessions = {}

def get_or_create_chat_session(user_id):
    if user_id not in user_gemini_sessions:
        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash-lite",
            generation_config=generation_config,
        )
        user_gemini_sessions[user_id] = model.start_chat(history=[])
    return user_gemini_sessions[user_id]


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text
    user_message_lower = user_message.lower()

    messages_to_reply = []
    final_bot_text_response = ""

    gemini_chat_session = get_or_create_chat_session(user_id)
    responded_by_gemini_direct = False

    # --- Phase 1: Rule-based Responses ---
    if user_message_lower in ['สวัสดี', 'นี่ใคร'] or user_message_lower.startswith('สวัสดี'):
        final_bot_text_response = "สวัสดีค่ะ KMUTNB Buddy ยินดีให้บริการ"
    
    # 2. ตรวจสอบคำถามที่ต้องการข้อมูลการติดต่อ (ปรับปรุง Logic หลักตรงนี้)
    elif any(kw in user_message_lower for kw in ['เบอร์โทร', 'โทรศัพท์', 'ติดต่อ', 'อีเมล', 'email', 'ช่องทางติดต่อ', 'เบอร์', 'อาจารย์', 'บุคลากร']):
        
        response_parts = []
        found_actionable_info = False # Flag เพื่อบอกว่าเจอข้อมูลที่นำไปสร้างคำตอบได้แล้ว
        
        list_explicit_keywords = ['รายชื่อ', 'ทั้งหมด', 'ทุกคน', 'บุคลากรของ', 'อาจารย์ใน']
        general_teacher_keywords = ['อาจารย์', 'บุคลากร'] # คำทั่วไปที่ใช้ถามถึงอาจารย์

        # --- Sub-Stage A: ระบุคณะ/ภาควิชาเป้าหมาย (เฉพาะเจาะจง) ก่อนเสมอ ---
        # ตัวอย่าง: "คณะวิทยาศาสตร์ประยุกต์" หรือ "คณะครุศาสตร์อุตสาหกรรม (ภาคคอมพิวเตอร์ศึกษา)"
        target_specific_dept_name = None
        for dept_name, dept_data in contact_info_db.items():
            if any(k.lower() in user_message_lower for k in dept_data["keywords"]):
                target_specific_dept_name = dept_name
                break

        # --- Sub-Stage B: ตรวจสอบกรณี "คณะครุศาสตร์อุตสาหกรรม" แบบกว้างๆ (ต้องแนะนำภาควิชา) ---
        # หากไม่พบภาควิชาที่เจาะจง และผู้ใช้ถามถึง "ครุศาสตร์" + "อาจารย์/บุคลากร" + "รายชื่อ/ทั้งหมด"
        if not target_specific_dept_name and \
           any(gk in user_message_lower for gk in ["ครุศาสตร์อุตสาหกรรม", "ครุศาสตร์"]) and \
           any(lk in user_message_lower for lk in general_teacher_keywords + list_explicit_keywords):
            
            response_parts.append("คณะครุศาสตร์อุตสาหกรรมมีหลายภาควิชาค่ะ")
            response_parts.append("โปรดระบุภาควิชาที่ต้องการให้ชัดเจน เช่น:")
            
            kru_sart_branches = []
            for dept_key, dept_val in contact_info_db.items():
                # ดึงชื่อภาควิชาของคณะครุศาสตร์อุตสาหกรรมทั้งหมด
                if dept_key.startswith("คณะครุศาสตร์อุตสาหกรรม (") and "ภาค" in dept_key:
                    branch_part = dept_key.replace("คณะครุศาสตร์อุตสาหกรรม (", "").replace(")", "")
                    kru_sart_branches.append(branch_part)
            
            if kru_sart_branches:
                # ตัวอย่าง: - คอมพิวเตอร์ศึกษา, เครื่องกล, ไฟฟ้า, โยธา
                response_parts.append("- " + ", ".join(kru_sart_branches))
            else:
                response_parts.append("- คอมพิวเตอร์ศึกษา, เครื่องกล, ไฟฟ้า, โยธา, เป็นต้น") # Fallback หากดึงสาขาไม่ได้
            response_parts.append("เพื่อฉันจะได้ค้นหาข้อมูลให้คุณได้ถูกต้องค่ะ")
            found_actionable_info = True # ถือว่าเจอข้อมูลที่ตอบได้แล้ว

        # --- Sub-Stage C: หากไม่ใช่กรณีข้างต้น, ให้ค้นหาบุคลากรเฉพาะเจาะจงด้วยชื่อเต็ม/ชื่อที่ชัดเจน ---
        # (จะทำงานก็ต่อเมื่อมี target_specific_dept_name และยังไม่พบ actionable info จาก Sub-Stage B)
        specific_person_match = None
        if not found_actionable_info and target_specific_dept_name:
            dept_data = contact_info_db[target_specific_dept_name]
            for person_name, person_data in dept_data.get("บุคลากร", {}).items():
                if person_name.lower() in user_message_lower: # ตรวจสอบชื่อเต็ม
                    specific_person_match = (person_name, person_data, target_specific_dept_name)
                    break
        
        if specific_person_match:
            person_name, person_data, dept_name = specific_person_match
            response_parts.append(f"ข้อมูลติดต่อสำหรับ {person_data['ตำแหน่ง']} {person_name} (สังกัด{dept_name}):")
            
            contact_details_list = []
            phone_info = person_data.get("เบอร์โทร")
            email_info = person_data.get("อีเมล")
            
            if phone_info: contact_details_list.append(f"โทร: {phone_info}")
            if email_info: contact_details_list.append(f"อีเมล: {email_info}")
            
            # ปรับการแสดงผล: ไม่ต้องมีวงเล็บรอบทั้งหมด
            response_parts.append(", ".join(contact_details_list) if contact_details_list else "ไม่พบข้อมูลการติดต่อที่ระบุค่ะ")
            found_actionable_info = True

        # --- Sub-Stage D: หากไม่เจอคนเฉพาะเจาะจง (Sub-Stage C), แต่มีคณะที่เจาะจง และถามถึงอาจารย์/บุคลากรทั้งหมด ---
        elif not found_actionable_info and target_specific_dept_name and \
             any(lk in user_message_lower for lk in general_teacher_keywords + list_explicit_keywords):
            
            dept_data = contact_info_db[target_specific_dept_name]
            response_parts.append(f"รายชื่อบุคลากรใน {target_specific_dept_name}:")
            
            if dept_data.get("บุคลากร"):
                for person_name, person_data in dept_data["บุคลากร"].items():
                    contact_details_list = []
                    phone_info = person_data.get("เบอร์โทร")
                    email_info = person_data.get("อีเมล")
                    if phone_info: contact_details_list.append(f"โทร: {phone_info}")
                    if email_info: contact_details_list.append(f"อีเมล: {email_info}")
                    
                    # ยังคงมีวงเล็บสำหรับแต่ละคนในลิสต์ เพื่อความเป็นระเบียบ
                    details_str_for_list = ", ".join(contact_details_list) if contact_details_list else "ไม่ระบุ"
                    response_parts.append(f"- {person_data['ตำแหน่ง']} {person_name} ({details_str_for_list})")
                found_actionable_info = True
            else:
                response_parts.append("ไม่พบข้อมูลบุคลากรในคณะนี้ค่ะ")
                found_actionable_info = True
        
        # --- Sub-Stage E: หากไม่เข้ากรณีใดๆ ข้างต้น แต่มีคณะที่เจาะจง ---
        # ให้ข้อมูลติดต่อส่วนกลางของคณะ
        elif not found_actionable_info and target_specific_dept_name:
            dept_data = contact_info_db[target_specific_dept_name]
            response_parts.append(f"ข้อมูลติดต่อสำหรับ {target_specific_dept_name}:")
            if dept_data.get("เบอร์กลาง"):
                response_parts.append(f"  เบอร์โทรศัพท์ส่วนกลาง: {dept_data['เบอร์กลาง']}")
            else:
                response_parts.append("  ไม่พบเบอร์โทรศัพท์ส่วนกลางที่ระบุค่ะ")
            response_parts.append(f"หากต้องการข้อมูลของบุคลากรเฉพาะเจาะจง หรือรายชื่อทั้งหมด โปรดระบุให้ชัดเจนยิ่งขึ้นค่ะ หรือดูรายละเอียดเพิ่มเติมในเอกสาร '1.2 ข้อมูลการติดต่ออาจารย์และเจ้าหน้าที่คณะต่างๆ'")
            found_actionable_info = True

        # --- สรุปคำตอบสุดท้ายสำหรับคำถามติดต่อจาก Rule-based ---
        if found_actionable_info:
            final_bot_text_response = "\n".join(response_parts)
        else:
            final_bot_text_response = (
                "ขออภัยค่ะ ฉันไม่พบข้อมูลติดต่อสำหรับสิ่งที่คุณกำลังมองหา\n\n"
                "คุณสามารถลองระบุชื่อบุคคล ตำแหน่ง หรือชื่อคณะ/ภาควิชาให้ชัดเจนยิ่งขึ้นได้ไหมคะ "
                "เช่น 'เบอร์โทรอาจารย์ยุพาภรณ์', 'รายชื่ออาจารย์คณะวิทยาศาสตร์ประยุกต์' หรือ 'ติดต่อคณะศิลปศาสตร์ประยุกต์' "
                "หรือดูในเอกสาร '1.2 ข้อมูลการติดต่ออาจารย์และเจ้าหน้าที่คณะต่างๆ' ค่ะ"
            )
    
    # 3. หากเจอคีย์เวิร์ด "การแต่งกาย"
    elif "การแต่งกาย" in user_message_lower:
        ai_response_text = answer_question(user_message) 
        
        if ai_response_text and ai_response_text.strip() != "":
            final_bot_text_response = ai_response_text
        else:
            final_bot_text_response = "ขออภัยค่ะ ฉันไม่พบข้อมูลการแต่งกายที่เฉพาะเจาะจง"
        
        messages_to_reply.append(TextMessage(text=final_bot_text_response))
        
        image_urls = [
            "https://i.postimg.cc/pL5wW60S/492254752-1212904400841195-3294721946119439077-n.jpg",
            # เพิ่ม URL รูปภาพการแต่งกายอื่นๆ ที่นี่
        ]
        for url in image_urls:
            messages_to_reply.append(ImageMessage(original_content_url=url, preview_image_url=url))

    # 4. หากเจอคีย์เวิร์ด "แผนที่"
    elif "แผนที่" in user_message_lower:
        ai_response_text = answer_question(user_message)
        
        if ai_response_text and ai_response_text.strip() != "":
            final_bot_text_response = ai_response_text
        else:
            final_bot_text_response = "นี่คือแผนที่มหาวิทยาลัยเทคโนโลยีพระจอมเกล้าพระนครเหนือค่ะ"
        
        messages_to_reply.append(TextMessage(text=final_bot_text_response))
        
        map_image_urls = [
         "https://i.postimg.cc/mrjfJFX0/481452366-3893729620865001-8488278701718064335-n.jpg", # แผนที่หลักของ มจพ.
        ]
        for url in map_image_urls:
            messages_to_reply.append(ImageMessage(original_content_url=url, preview_image_url=url))
    
    # 5. สำหรับคำถามอื่นๆ ที่เป็น Generic เช่น ขอบคุณ, จบการสนทนา
    elif any(keyword in user_message_lower for keyword in ['ขอบคุณ', 'พอแล้ว', 'จบการสนทนา', 'บาย', 'ไปละ']):
        final_bot_text_response = "ยินดีให้บริการค่ะ หากมีคำถามเพิ่มเติม สามารถสอบถามได้ตลอดนะคะ"

    # --- Phase 2: RAG / Gemini Fallback if no rule-based response yet ---
    if not final_bot_text_response:
        app.logger.info(f"No rule-based response for '{user_message}', attempting RAG.")
        ai_response_text = answer_question(user_message)
        
        if ai_response_text and ai_response_text.strip() != "":
            final_bot_text_response = ai_response_text
        else:
            app.logger.info(f"RAG did not find an answer for '{user_message}', falling back to Gemini direct.")
            try:
                gemini_response = gemini_chat_session.send_message(user_message)
                final_bot_text_response = gemini_response.text
                responded_by_gemini_direct = True
                app.logger.info(f"Gemini direct response for '{user_message}': {final_bot_text_response[:50]}...")
            except Exception as e:
                app.logger.error(f"Error getting direct Gemini response for user {user_id}: {e}")
                final_bot_text_response = "ขออภัยค่ะ ฉันไม่เข้าใจคำถามของคุณ โปรดลองถามในรูปแบบอื่นนะคะ"
    
    # --- Phase 3: Ensure a text message is always added to messages_to_reply ---
    if not messages_to_reply and final_bot_text_response:
        messages_to_reply.append(TextMessage(text=final_bot_text_response))
    elif not messages_to_reply and not final_bot_text_response:
        final_bot_text_response = "ขออภัยค่ะ ฉันไม่เข้าใจคำถามของคุณ โปรดลองถามในรูปแบบอื่นนะคะ"
        messages_to_reply.append(TextMessage(text=final_bot_text_response))


    # --- Phase 4: Manually add history to Gemini if not handled by send_message ---
    if not responded_by_gemini_direct:
        if user_message and final_bot_text_response:
            try:
                gemini_chat_session.history.append(genai.types.Content(parts=[genai.types.TextPart(user_message)], role="user"))
                gemini_chat_session.history.append(genai.types.Content(parts=[genai.types.TextPart(final_bot_text_response)], role="model"))
                app.logger.info(f"Manually added user and bot response to Gemini history for user {user_id}.")
            except Exception as e:
                app.logger.error(f"Failed to manually add history for user {user_id}: {e}")
    else:
        app.logger.info(f"Gemini direct response handled history for user {user_id}.")


    # ส่งข้อความและ/หรือรูปภาพตอบกลับไปยัง LINE
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=messages_to_reply
            )
        )

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

    
    