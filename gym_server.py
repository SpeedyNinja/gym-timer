from flask import Flask, request, jsonify
from datetime import datetime
import requests

app = Flask(__name__)

# --- 설정 정보 입력 ---
BOT_TOKEN = "8744185006:AAHTQG4HW6bsH1D8PVRTfLOmPzkcGv0Dbbg"
CHAT_ID = "8376898865"

# 운동 시작 시간을 임시 저장할 전역 변수
start_time = None

def send_telegram(message):
    """텔레그램 메시지 발송 함수"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"텔레그램 전송 에러: {e}")

@app.route("/gym/enter", methods=["POST"])
def enter_gym():
    """헬스장 도착 시 호출되는 API"""
    global start_time
    start_time = datetime.now()
    now_str = start_time.strftime("%H시 %M분")
    
    msg = f"🏋️ [운동 시작]\n도착 시간: {now_str}\n오늘도 득근하세요!"
    send_telegram(msg)
    return jsonify({"status": "started", "time": now_str}), 200

@app.route("/gym/exit", methods=["POST"])
def exit_gym():
    """헬스장 이탈 시 호출되는 API"""
    global start_time
    
    if start_time is None:
        send_telegram("⚠️ 운동 시작 기록이 없습니다. 종료 시간만 감지되었습니다.")
        return jsonify({"status": "no start time"}), 400

    end_time = datetime.now()
    duration = end_time - start_time
    
    # 시간 및 분 계산
    total_seconds = int(duration.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60

    # 소요 시간 포맷팅
    if hours > 0:
        time_text = f"{hours}시간 {minutes}분"
    else:
        time_text = f"{minutes}분"

    msg = f"🏆 [운동 완료]\n총 소요 시간: {time_text}\n수고하셨습니다!"
    send_telegram(msg)
    
    # 다음 기록을 위해 초기화
    start_time = None
    return jsonify({"status": "finished", "duration": time_text}), 200

if __name__ == "__main__":
    # 외부 기기(아이폰)에서 접속 가능하도록 0.0.0.0으로 실행
    app.run(host="0.0.0.0", port=5000)