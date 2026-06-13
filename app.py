import asyncio
import re
from telethon import TelegramClient
from telethon.tl.functions.channels import JoinChannelRequest
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

# ==========================================
# CẤU HÌNH THÔNG TIN TỪ MY.TELEGRAM.ORG
# ==========================================
API_ID = 33207171                  # Thay bằng số api_id của bạn (kiểu int)
API_HASH = '9f1dfc1c5e6860558866ec6ff95e4aab'      # Thay bằng chuỗi api_hash của bạn (kiểu string)
PHONE_NUMBER = '+19299335640'      # VUI LÒNG ĐIỀN LẠI SỐ ĐIỆN THOẠI CỦA BẠN

# Tên file để lưu trữ phiên đăng nhập (giúp các lần sau chạy không cần nhập lại OTP)
SESSION_FILE = 'my_personal_session'

# ==========================================
# KHỞI TẠO SERVER FLASK
# ==========================================
app = Flask(__name__)
# Bật CORS để cho phép Frontend (HTML) gọi API này mà không bị lỗi bảo mật của trình duyệt
CORS(app)

# ==========================================
# HÀM XỬ LÝ TELEGRAM (TELETHON)
# ==========================================
async def send_telegram_request(web_phone_number):
    """Hàm xử lý Telegram: Nhận diện siêu chuẩn xác qua ID Người dùng và Reply Message"""
    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)

    print("⏳ Đang kết nối đến Telegram...")
    await client.start(phone=PHONE_NUMBER)
    print("✅ Đăng nhập thành công!")

    # TỰ ĐỘNG LẤY ID CỦA TÀI KHOẢN (Chính là số 7212428335 của bạn)
    me = await client.get_me()
    my_id = str(me.id)

    # ⚠️ LƯU Ý: Vui lòng điền đúng link nhóm của bạn vào đây
    group_username = 'https://t.me/SpamCallPro'

    try:
        # Bước 1: Tham gia nhóm
        print(f"⏳ Đang tham gia nhóm @{group_username}...")
        await client(JoinChannelRequest(group_username))
        print("✅ Đã tham gia nhóm!")

        await asyncio.sleep(2)

        # Xóa khoảng trắng thừa của SĐT để check chính xác
        clean_phone = str(web_phone_number).strip()
        last_3_digits = clean_phone[-3:]

        # Bước 2: Gửi lệnh /spam kèm SĐT
        message_to_send = f'/spam {clean_phone}'
        print(f"⏳ Đang gửi lệnh: {message_to_send}...")
        
        # Lưu lại tin nhắn mình vừa gửi để lát check xem Bot có Reply lại đúng tin này không
        sent_msg = await client.send_message(group_username, message_to_send)
        sent_msg_id = sent_msg.id
        
        print(f"✅ Đã gửi lệnh! Đang theo dõi ID: {my_id} hoặc Reply ID: {sent_msg_id}...")

        # Bước 3: Chờ Bot phản hồi (TỐI ĐA 30 GIÂY)
        bot_reply = None
        is_cooldown = False 

        for _ in range(30):
            await asyncio.sleep(1) 
            # Quét 30 tin nhắn mới nhất để không bị trôi
            messages = await client.get_messages(group_username, limit=30)
            
            for msg in messages:
                if not msg.text:
                    continue
                
                text = msg.text
                text_lower = text.lower()
                
                # TRƯỜNG HỢP 1: THÀNH CÔNG (NHẬN DIỆN VÔ ĐỊCH)
                # Dùng tuyệt chiêu của bạn: Tìm thẳng ID 7212428335 trong tin nhắn + 3 số cuối
                has_id_and_phone = (my_id in text and last_3_digits in text)
                
                # Hoặc kiểm tra xem tin nhắn của Bot có phải là Reply tin nhắn của mình không
                is_reply = (msg.reply_to is not None and msg.reply_to.reply_to_msg_id == sent_msg_id)

                if has_id_and_phone or is_reply:
                    bot_reply = text
                    break
                
                # TRƯỜNG HỢP 2: COOLDOWN (Bot báo đang spam)
                if 'spam' in text_lower and clean_phone in text_lower:
                    bot_reply = text
                    is_cooldown = True
                    break
            
            if bot_reply: # Đã tìm thấy, thoát vòng lặp
                break
        
        if bot_reply:
            if is_cooldown:
                return False, bot_reply 
            else:
                return True, bot_reply  
        else:
            return False, "Bot không phản hồi sau 30 giây (Đã quét 30 tin mới nhất)."

    except Exception as e:
        print(f"❌ Có lỗi xảy ra trong quá trình thực thi: {e}")
        return False, str(e)
        
    finally:
        await client.disconnect()

# ==========================================
# ROUTE CHO TRANG CHỦ (GIAO DIỆN WEB)
# ==========================================
@app.route('/', methods=['GET'])
def home():
    return render_template('index.html')

# ==========================================
# API ENDPOINT ĐỂ WEB GỌI VÀO
# ==========================================
@app.route('/api/submit_phone', methods=['POST'])
def handle_phone_number():
    data = request.json
    phone_number = data.get('phone_number')
    web_user = data.get('web_user', 'Khách')

    if not phone_number:
        return jsonify({"status": "error", "message": "Thiếu số điện thoại!"}), 400

    print(f"📲 Nhận được SĐT từ Web: {phone_number} (Tài khoản: {web_user})")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    success, result_message = loop.run_until_complete(send_telegram_request(phone_number))
    loop.close()

    if success:
        # TRÍCH XUẤT DỮ LIỆU THÔNG MINH (Không dùng chữ ID hay Phone nữa)
        
        # 1. Bắt chuỗi số bị che (Ví dụ: 0927***855) có chứa dấu *
        masked_phone_match = re.search(r'([0-9\+]+[\*]+[0-9]+)', result_message)
        bot_phone = masked_phone_match.group(1) if masked_phone_match else phone_number
        
        # 2. Bắt ID (Là một dãy số dài từ 8 đến 12 số đứng liền nhau)
        id_match = re.search(r'([0-9]{8,12})', result_message)
        bot_id = id_match.group(1) if id_match else "7212428335"
        
        final_message = f"User: {web_user} ID:{bot_id} Phone: {bot_phone}"

        return jsonify({
            "status": "success", 
            "message": final_message
        }), 200
    else:
        # NẾU LÀ LỖI COOLDOWN HOẶC LỖI KHÔNG PHẢN HỒI
        return jsonify({
            "status": "error", 
            "message": result_message 
        }), 400

# ==========================================
# CHẠY SERVER FLASK
# ==========================================
if __name__ == '__main__':
    print("🚀 Server Python đang chạy tại http://0.0.0.0:5000")
    app.run(debug=False, host='0.0.0.0', port=5000)