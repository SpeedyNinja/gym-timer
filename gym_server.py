import calendar
from datetime import datetime, timedelta
import json
import os
import sqlite3
from zoneinfo import ZoneInfo
from flask import Flask, jsonify, redirect, render_template_string, request, url_for
import psycopg2
import psycopg2.extras
import requests

# 한국 시간대 지정 (KST)
KST = ZoneInfo("Asia/Seoul")

app = Flask(__name__)

# --- 설정 정보 ---
BOT_TOKEN = "8744185006:AAHTQG4HW6bsH1D8PVRTfLOmPzkcGv0Dbbg"
CHAT_ID = "8376898865"
DATABASE_URL = os.environ.get("DATABASE_URL")

start_time = None


def get_db_connection():
  """PostgreSQL DB 연결 객체 반환 (미설정 시 로컬 sqlite 대체)"""
  if DATABASE_URL:
    return psycopg2.connect(DATABASE_URL)
  else:
    return sqlite3.connect("gym_records.db")


def init_db():
  """서버 시작 시 운동 기록 테이블 생성"""
  conn = get_db_connection()
  cursor = conn.cursor()

  if DATABASE_URL:
    cursor.execute("""
            CREATE TABLE IF NOT EXISTS gym_logs (
                id SERIAL PRIMARY KEY,
                date VARCHAR(20),
                start_time VARCHAR(10),
                end_time VARCHAR(10),
                duration VARCHAR(30),
                duration_minutes INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
  else:
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

  conn.commit()
  cursor.close()
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


# --- 모바일 웹 캘린더 대시보드 HTML 템플릿 ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <title>헬스 타이머 캘린더</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; -webkit-tap-highlight-color: transparent; }
        body { background-color: #121212; color: #FFFFFF; padding: 20px 16px 40px 16px; min-height: 100vh; }
        
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
        .header h1 { font-size: 20px; font-weight: 700; color: #FF9F0A; }
        .refresh-btn {
            background-color: #2C2C2E;
            color: #FFFFFF;
            border: 1px solid #3A3A3C;
            padding: 6px 12px;
            font-size: 13px;
            border-radius: 16px;
            cursor: pointer;
            font-weight: 600;
        }
        
        /* 탭 스타일 (열품타 느낌) */
        .tab-bar { display: flex; background-color: #1C1C1E; border-radius: 12px; padding: 4px; margin-bottom: 20px; }
        .tab-btn { flex: 1; text-align: center; padding: 8px 0; border: none; background: transparent; color: #8E8E93; font-size: 14px; font-weight: 600; border-radius: 8px; cursor: pointer; }
        .tab-btn.active { background-color: #FF9F0A; color: #121212; }
        
        /* 상단 통계 카드 */
        .stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 20px; }
        .stat-card { background-color: #1C1C1E; padding: 14px 12px; border-radius: 14px; text-align: center; border: 1px solid #2C2C2E; }
        .stat-card .label { font-size: 12px; color: #8E8E93; margin-bottom: 4px; }
        .stat-card .value { font-size: 18px; font-weight: 700; color: #30D158; }
        
        /* 캘린더 영역 */
        .calendar-card { background-color: #1C1C1E; border-radius: 16px; padding: 16px; border: 1px solid #2C2C2E; margin-bottom: 24px; }
        .calendar-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; font-weight: 700; font-size: 16px; }
        .weekdays { display: grid; grid-template-columns: repeat(7, 1fr); text-align: center; font-size: 12px; color: #8E8E93; margin-bottom: 8px; font-weight: 600; }
        .days-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 6px; }
        
        .day-cell {
            aspect-ratio: 1 / 1.15;
            background-color: #242426;
            border-radius: 8px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            color: #8E8E93;
            position: relative;
        }
        .day-cell.empty { background-color: transparent; }
        .day-cell.today { border: 1.5px solid #0A84FF; }
        .day-num { font-size: 11px; font-weight: 600; margin-bottom: 2px; }
        .day-time { font-size: 9px; font-weight: 700; color: #FFFFFF; text-align: center; line-height: 1; }
        
        /* 열품타 잔디 색상 단계 */
        .level-1 { background-color: rgba(255, 159, 10, 0.25) !important; color: #FFD60A; } /* ~45분 */
        .level-2 { background-color: rgba(255, 159, 10, 0.55) !important; color: #FFFFFF; } /* 45분~90분 */
        .level-3 { background-color: #FF9F0A !important; color: #121212 !important; }        /* 90분 이상 */
        .level-3 .day-time { color: #121212; }

        /* 주간 뷰 그리드 */
        .weekly-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 6px; }
        .week-day-cell {
            background-color: #242426;
            border-radius: 10px;
            padding: 10px 4px;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 6px;
        }
        .week-day-name { font-size: 12px; color: #8E8E93; font-weight: 600; }
        .week-day-date { font-size: 13px; font-weight: 700; }
        .week-day-time { font-size: 10px; font-weight: 700; color: #FF9F0A; text-align: center; }

        /* 최근 기록 리스트 */
        .section-title { font-size: 15px; font-weight: 600; margin-bottom: 12px; color: #E5E5EA; }
        .log-list { display: flex; flex-direction: column; gap: 10px; }
        .log-item { background-color: #1C1C1E; padding: 14px 16px; border-radius: 12px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #2C2C2E; }
        .log-date { font-weight: 600; font-size: 14px; margin-bottom: 2px; }
        .log-time { font-size: 12px; color: #8E8E93; }
        .log-right { display: flex; align-items: center; gap: 12px; }
        .log-duration { font-size: 14px; font-weight: 700; color: #FF9F0A; }
        .delete-btn { background-color: #3A1D1D; color: #FF453A; border: 1px solid #5A2727; padding: 5px 9px; font-size: 12px; border-radius: 8px; cursor: pointer; font-weight: 600; }
        .empty-log { text-align: center; color: #636366; padding: 20px 0; font-size: 13px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔥 운동 통계</h1>
        <button class="refresh-btn" onclick="window.location.reload();">🔄 새로고침</button>
    </div>

    <!-- 주간 / 월간 탭 선택 -->
    <div class="tab-bar">
        <button id="tab-week" class="tab-btn active" onclick="switchTab('week')">주간</button>
        <button id="tab-month" class="tab-btn" onclick="switchTab('month')">월간</button>
    </div>

    <!-- 통계 카드 -->
    <div class="stats-grid">
        <div class="stat-card">
            <div class="label">이번 주 총 운동</div>
            <div class="value">{{ weekly_total }}</div>
        </div>
        <div class="stat-card">
            <div class="label">이번 달 총 운동</div>
            <div class="value">{{ monthly_total }}</div>
        </div>
    </div>

    <!-- 주간 뷰 -->
    <div id="view-week" class="calendar-card">
        <div class="calendar-header">
            <span>이번 주 운동 현황</span>
            <span style="font-size: 12px; color: #8E8E93;">{{ week_range_str }}</span>
        </div>
        <div class="weekly-grid">
            {% for d in week_days %}
            <div class="week-day-cell {% if d.level > 0 %}level-{{ d.level }}{% endif %} {% if d.is_today %}today{% endif %}">
                <span class="week-day-name">{{ d.day_name }}</span>
                <span class="week-day-date">{{ d.day_num }}</span>
                <span class="week-day-time">{{ d.time_str if d.time_str else '-' }}</span>
            </div>
            {% endfor %}
        </div>
    </div>

    <!-- 월간 캘린더 뷰 (기본 숨김) -->
    <div id="view-month" class="calendar-card" style="display: none;">
        <div class="calendar-header">
            <span>{{ current_month_str }}</span>
        </div>
        <div class="weekdays">
            <span>일</span><span>월</span><span>화</span><span>수</span><span>목</span><span>금</span><span>토</span>
        </div>
        <div class="days-grid">
            {% for item in month_calendar %}
                {% if item.day == 0 %}
                    <div class="day-cell empty"></div>
                {% else %}
                    <div class="day-cell {% if item.level > 0 %}level-{{ item.level }}{% endif %} {% if item.is_today %}today{% endif %}">
                        <span class="day-num">{{ item.day }}</span>
                        {% if item.time_str %}
                            <span class="day-time">{{ item.time_str }}</span>
                        {% endif %}
                    </div>
                {% endif %}
            {% endfor %}
        </div>
    </div>

    <!-- 누적 내역 목록 및 삭제 -->
    <div class="section-title">최근 운동 기록</div>
    <div class="log-list">
        {% if logs %}
            {% for log in logs %}
            <div class="log-item">
                <div>
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
            <div class="empty-log">저장된 기록이 없습니다.</div>
        {% endif %}
    </div>

    <script>
        function switchTab(type) {
            const tabWeek = document.getElementById('tab-week');
            const tabMonth = document.getElementById('tab-month');
            const viewWeek = document.getElementById('view-week');
            const viewMonth = document.getElementById('view-month');

            if (type === 'week') {
                tabWeek.classList.add('active');
                tabMonth.classList.remove('active');
                viewWeek.style.display = 'block';
                viewMonth.style.display = 'none';
            } else {
                tabMonth.classList.add('active');
                tabWeek.classList.remove('active');
                viewWeek.style.display = 'none';
                viewMonth.style.display = 'block';
            }
        }

        // 아래로 당겨서 새로고침 (Pull to Refresh)
        let startY = 0;
        window.addEventListener('touchstart', function(e) {
            if (window.scrollY === 0) startY = e.touches[0].pageY;
            else startY = 0;
        }, { passive: true });

        window.addEventListener('touchend', function(e) {
            if (startY > 0 && e.changedTouches[0].pageY - startY > 120) {
                window.location.reload();
            }
        }, { passive: true });
    </script>
</body>
</html>
"""


def format_minutes_short(mins):
  """캘린더 타일용 짧은 시간 포맷팅 (예: 1h 25m, 40m)"""
  if not mins:
    return ""
  h = mins // 60
  m = mins % 60
  if h > 0 and m > 0:
    return f"{h}h {m}m"
  elif h > 0:
    return f"{h}h"
  else:
    return f"{m}m"


def format_minutes_long(mins):
  """통계 카드용 긴 시간 포맷팅 (예: 2시간 15분)"""
  if not mins:
    return "0분"
  h = mins // 60
  m = mins % 60
  if h > 0 and m > 0:
    return f"{h}시간 {m}분"
  elif h > 0:
    return f"{h}시간"
  else:
    return f"{m}분"


def get_heat_level(mins):
  """열품타 스타일 운동 시간에 따른 색상 레벨 (0~3)"""
  if mins <= 0:
    return 0
  if mins < 45:
    return 1  # 연한 주황
  elif mins < 90:
    return 2  # 보통 주황
  else:
    return 3  # 짙은 주황


@app.route("/", methods=["GET"])
def dashboard():
  """캘린더 및 통계 대시보드 화면"""
  now_kst = datetime.now(KST)
  today_str = now_kst.strftime("%Y-%m-%d")

  conn = get_db_connection()
  cursor = conn.cursor()

  # 최근 전체 로그 조회
  cursor.execute(
      "SELECT id, date, start_time, end_time, duration, duration_minutes FROM"
      " gym_logs ORDER BY id DESC"
  )
  logs = cursor.fetchall()

  # 날짜별 운동 시간 합산 맵 (YYYY-MM-DD -> 총 분)
  cursor.execute(
      "SELECT date, SUM(duration_minutes) FROM gym_logs GROUP BY date"
  )
  date_minutes_map = {row[0]: (row[1] or 0) for row in cursor.fetchall()}

  # --- 주간 데이터 계산 (이번 주 월 ~ 일) ---
  monday = now_kst - timedelta(days=now_kst.weekday())
  sunday = monday + timedelta(days=6)
  week_range_str = (
      f"{monday.strftime('%m/%d')} ~ {sunday.strftime('%m/%d')}"
  )

  week_days = []
  weekly_total_minutes = 0
  day_names = ["월", "화", "수", "목", "금", "토", "일"]

  for i in range(7):
    day_date = monday + timedelta(days=i)
    day_str = day_date.strftime("%Y-%m-%d")
    m = date_minutes_map.get(day_str, 0)
    weekly_total_minutes += m
    week_days.append({
        "day_name": day_names[i],
        "day_num": day_date.strftime("%d"),
        "time_str": format_minutes_short(m),
        "level": get_heat_level(m),
        "is_today": (day_str == today_str),
    })

  # --- 월간 캘린더 데이터 계산 ---
  current_month_str = now_kst.strftime("%Y년 %m월")
  month_prefix = now_kst.strftime("%Y-%m-")

  # 일요일 시작 달력 생성
  cal = calendar.Calendar(firstweekday=6)
  month_calendar = []
  monthly_total_minutes = 0

  for date_obj in cal.itermonthdates(now_kst.year, now_kst.month):
    if date_obj.month != now_kst.month:
      month_calendar.append({"day": 0})
    else:
      d_str = date_obj.strftime("%Y-%m-%d")
      m = date_minutes_map.get(d_str, 0)
      monthly_total_minutes += m
      month_calendar.append({
          "day": date_obj.day,
          "time_str": format_minutes_short(m),
          "level": get_heat_level(m),
          "is_today": (d_str == today_str),
      })

  cursor.close()
  conn.close()

  return render_template_string(
      HTML_TEMPLATE,
      logs=logs,
      weekly_total=format_minutes_long(weekly_total_minutes),
      monthly_total=format_minutes_long(monthly_total_minutes),
      week_days=week_days,
      week_range_str=week_range_str,
      current_month_str=current_month_str,
      month_calendar=month_calendar,
  )


@app.route("/gym/delete/<int:log_id>", methods=["POST"])
def delete_log(log_id):
  """운동 기록 삭제 API"""
  conn = get_db_connection()
  cursor = conn.cursor()
  if DATABASE_URL:
    cursor.execute("DELETE FROM gym_logs WHERE id = %s", (log_id,))
  else:
    cursor.execute("DELETE FROM gym_logs WHERE id = ?", (log_id,))
  conn.commit()
  cursor.close()
  conn.close()
  return redirect(url_for("dashboard"))


@app.route("/gym/enter", methods=["POST"])
def enter_gym():
  """운동 시작 API"""
  global start_time
  start_time = datetime.now(KST)
  now_str = start_time.strftime("%H시 %M분")

  msg = f"🏋️ [운동 시작]\n도착 시간: {now_str}\n오늘도 득근하세요!"
  send_telegram(msg)
  return jsonify({"status": "started", "time": now_str}), 200


@app.route("/gym/exit", methods=["POST"])
def exit_gym():
  """운동 종료 API: 시간 계산 + PostgreSQL 영구 저장"""
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

  try:
    conn = get_db_connection()
    cursor = conn.cursor()
    if DATABASE_URL:
      cursor.execute(
          """
                INSERT INTO gym_logs (date, start_time, end_time, duration, duration_minutes)
                VALUES (%s, %s, %s, %s, %s)
            """,
          (date_str, start_str, end_str, time_text, duration_minutes),
      )
    else:
      cursor.execute(
          """
                INSERT INTO gym_logs (date, start_time, end_time, duration, duration_minutes)
                VALUES (?, ?, ?, ?, ?)
            """,
          (date_str, start_str, end_str, time_text, duration_minutes),
      )
    conn.commit()
    cursor.close()
    conn.close()
  except Exception as e:
    print(f"DB 저장 에러: {e}")

  msg = f"🏆 [운동 완료]\n총 소요 시간: {time_text}\n기록이 안전하게 저장되었습니다!"
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
