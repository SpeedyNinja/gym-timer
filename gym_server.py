from datetime import datetime, timedelta
import sqlite3
from zoneinfo import ZoneInfo
from flask import Flask, jsonify, redirect, render_template_string, request, url_for
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
            duration_minutes INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
  # 기존 테이블에 duration_minutes 컬럼이 없을 경우를 대비한 마이그레이션
  cursor.execute("PRAGMA table_info(gym_logs)")
  columns = [col[1] for col in cursor.fetchall()]
  if "duration_minutes" not in columns:
    cursor.execute(
        "ALTER TABLE gym_logs ADD COLUMN duration_minutes INTEGER DEFAULT 0"
    )

  conn.commit()
  conn.close()


init_db()


def send_telegram(message):
  """텔레그램 메시지 발송 함수"""
  url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
  payload = {"chat_id": CHAT_ID, "text": message}
  try:
    requests.post(url, data=payload)
  except Exception as e:
    print(f"텔레그램 전송 에러: {e}")


# --- 모바일 웹 대시보드 HTML 템플릿 ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <title>헬스 타이머 대시보드</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        body { background-color: #121212; color: #FFFFFF; padding: 20px 16px; }
        .header { margin-bottom: 20px; text-align: center; }
        .header h1 { font-size: 22px; font-weight: 700; color: #4E95FF; }
        
        .stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 24px; }
        .stat-card { background-color: #1E1E1E; padding: 16px 12px; border-radius: 14px; text-align: center; border: 1px solid #2C2C2E; }
        .stat-card .label { font-size: 13px; color: #8E8E93; margin-bottom: 6px; }
        .stat-card .value { font-size: 18px; font-weight: 700; color: #30D158; }
        
        .section-title { font-size: 16px; font-weight: 600; margin-bottom: 12px; color: #E5E5EA; }
        .log-list { display: flex; flex-direction: column; gap: 10px; }
        .log-item { background-color: #1E1E1E; padding: 14px 16px; border-radius: 12px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #2C2C2E; }
        .log-info { display: flex; flex-direction: column; gap: 4px; }
        .log-date { font-weight: 600; font-size: 15px; }
        .log-time { font-size: 12px; color: #8E8E93; }
        .log-right { display: flex; align-items: center; gap: 12px; }
        .log-duration { font-size: 15px; font-weight: 700; color: #FF9F0A; }
        
        .delete-btn {
            background-color: #3A1D1D;
            color: #FF453A;
            border: 1px solid #5A2727;
            padding: 6px 10px;
            font-size: 12px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
        }
        .empty-log { text-align: center; color: #636366; padding: 30px 0; font-size: 14px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🏋️ 운동 기록 대시보드</h1>
    </div>

    <!-- 통계 카드: 이번 주 총 시간 & 총 횟수 -->
    <div class="stats-grid">
        <div class="stat-card">
            <div class="label">이번 주 총 운동</div>
            <div class="value">{{ weekly_total }}</div>
        </div>
        <div class="stat-card">
            <div class="label">총 누적 횟수</div>
            <div class="value">{{ total_count }}회</div>
        </div>
    </div>

    <!-- 기록 목록 -->
    <div class="section-title">최근 운동 내역</div>
    <div class="log-list">
        {% if logs %}
            {% for log in logs %}
            <div class="log-item">
                <div class="log-info">
                    <div class="log-date">{{ log[1] }}</div>
                    <div class="log-time">{{ log[2] }} ~ {{ log[3] }}</div>
                </div>
                <div class="log-right">
                    <div class="log-duration">{{ log[4] }}</div>
                    <form action="/gym/delete/{{ log[0] }}" method="POST" onsubmit="return confirm('이 기록을 삭제하시겠습니까?');">
                        <button type="submit" class="delete-btn">삭제</button>
                    </form>
                </div>
            </div>
            {% endfor %}
        {% else %}
            <div class="empty-log">아직 저장된 운동 기록이 없습니다.</div>
        {% endif %}
    </div>
</body>
</html>
"""


@app.route("/", methods=["GET"])
def dashboard():
  """웹 브라우저 접속 시 기록 목록 및 주간 통계 화면 표시"""
  now_kst = datetime.now(KST)

  # 이번 주 월요일 계산
  monday = (now_kst - timedelta(days=now_kst.weekday())).strftime("%Y-%m-%d")

  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()

  # 전체 기록 목록 (최신순)
  cursor.execute(
      "SELECT id, date, start_time, end_time, duration, duration_minutes FROM"
      " gym_logs ORDER BY id DESC"
  )
  logs = cursor.fetchall()

  # 이번 주(월요일 이후) 총 운동 분(minutes) 합산
  cursor.execute(
      "SELECT SUM(duration_minutes) FROM gym_logs WHERE date >= ?", (monday,)
  )
  weekly_minutes = cursor.fetchone()[0] or 0

  conn.close()

  # 주간 운동 시간 텍스트 변환
  w_hours = weekly_minutes // 60
  w_mins = weekly_minutes % 60
  if w_hours > 0:
    weekly_total = f"{w_hours}시간 {w_mins}분"
  elif w_mins > 0:
    weekly_total = f"{w_mins}분"
  else:
    weekly_total = "0분"

  return render_template_string(
      HTML_TEMPLATE,
      logs=logs,
      total_count=len(logs),
      weekly_total=weekly_total,
  )


@app.route("/gym/delete/<int:log_id>", methods=["POST"])
def delete_log(log_id):
  """운동 기록 삭제 API"""
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute("DELETE FROM gym_logs WHERE id = ?", (log_id,))
  conn.commit()
  conn.close()

  # 삭제 후 메인 대시보드로 새로고침 리다이렉트
  return redirect(url_for("dashboard"))


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
  duration_minutes = total_seconds // 60
  hours = total_seconds // 3600
  minutes = (total_seconds % 3600) // 60

  time_text = f"{hours}시간 {minutes}분" if hours > 0 else f"{minutes}분"

  date_str = start_time.strftime("%Y-%m-%d")
  start_str = start_time.strftime("%H:%M")
  end_str = end_time.strftime("%H:%M")

  # DB 저장 (총 운동 분 단위 컬럼 추가)
  try:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
            INSERT INTO gym_logs (date, start_time, end_time, duration, duration_minutes)
            VALUES (?, ?, ?, ?, ?)
        """,
        (date_str, start_str, end_str, time_text, duration_minutes),
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
