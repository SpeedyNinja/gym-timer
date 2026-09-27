import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, jsonify, request
import requests

# 한국 시간대 지정 (KST)
KST = ZoneInfo("Asia/Seoul")

app = Flask(__name__)

# --- 설정 정보 ---
BOT_TOKEN = "8744185006:AAHTQG4HW6bsH1D8PVRTfLOmPzkcGv0Dbbg"
CHAT_ID = "8376898865"
DB_NAME = "gym_records.db"

start_time = None

def init_db():
  """서버 시작 시 운동 기록 테이블 생성"""
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS gym_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            start_time TEXT,
            end_time TEXT,
            duration TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
  conn.commit()
  conn.close()

# 서버 구동 시 DB 초기화 실행
init_db()

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
  """헬스장 도착 시 호출"""
  global start_time
  start_time = datetime.now(KST)
  now_str = start_time.strftime("%H시 %M분")

  msg = f"🏋️ [운동 시작]\n도착 시간: {now_str}\n오늘도 득근하세요!"
  send_telegram(msg)
  return jsonify({"status": "started", "time": now_str}), 200

@app.route("/gym/exit", methods=["POST"])
def exit_gym():
  """헬스장 이탈 시 호출: 소요 시간 계산 + DB 저장"""
  global start_time

  if start_time is None:
    send_telegram("⚠️ 운동 시작 기록이 없습니다. 종료 시간만 감지되었습니다.")
    return jsonify({"status": "no start time"}), 400

  end_time = datetime.now(KST)
  duration = end_time - start_time

  total_seconds = int(duration.total_seconds())
  hours = total_seconds // 3600
  minutes = (total_seconds % 3600) // 60

  time_text = f"{hours}시간 {minutes}분" if hours > 0 else f"{minutes}분"

  # 날짜 및 시간 텍스트 포맷
  date_str = start_time.strftime("%Y-%m-%d")
  start_str = start_time.strftime("%H:%M")
  end_str = end_time.strftime("%H:%M")

  # --- DB에 운동 기록 저장 ---
  try:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
            INSERT INTO gym_logs (date, start_time, end_time, duration)
            VALUES (?, ?, ?, ?)
        """,
        (date_str, start_str, end_str, time_text),
    )
    conn.commit()
    conn.close()
  except Exception as e:
    print(f"DB 저장 에러: {e}")

  msg = f"🏆 [운동 완료]\n총 소요 시간: {time_text}\n기록이 저장되었습니다!"
  send_telegram(msg)

  start_time = None
  return (
      jsonify(
          {"status": "finished", "duration": time_text, "date": date_str}
      ),
      200,
  )

if __name__ == "__main__":
  app.run(host="0.0.0.0", port=5000)
