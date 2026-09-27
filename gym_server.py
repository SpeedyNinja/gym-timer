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

KST = ZoneInfo("Asia/Seoul")

app = Flask(__name__)

# --- 설정 정보 ---
BOT_TOKEN = "8744185006:AAHTQG4HW6bsH1D8PVRTfLOmPzkcGv0Dbbg"
CHAT_ID = "8376898865"
DATABASE_URL = os.environ.get("DATABASE_URL")

start_time = None

def get_db_connection():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL)
    else:
        return sqlite3.connect("gym_records.db")

def init_db():
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
                body_part VARCHAR(100) DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name='gym_logs' AND column_name='body_part'
        """)
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE gym_logs ADD COLUMN body_part VARCHAR(100) DEFAULT ''")
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gym_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                start_time TEXT,
                end_time TEXT,
                duration TEXT,
                duration_minutes INTEGER DEFAULT 0,
                body_part TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("PRAGMA table_info(gym_logs)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'body_part' not in columns:
            cursor.execute("ALTER TABLE gym_logs ADD COLUMN body_part TEXT DEFAULT ''")

    conn.commit()
    cursor.close()
    conn.close()

init_db()

def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"텔레그램 전송 에러: {e}")

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
        body { background-color: #121212; color: #FFFFFF; padding: 20px 16px 60px 16px; min-height: 100vh; }
        
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
        
        .tab-bar { display: flex; background-color: #1C1C1E; border-radius: 12px; padding: 4px; margin-bottom: 20px; }
        .tab-btn { flex: 1; text-align: center; padding: 8px 0; border: none; background: transparent; color: #8E8E93; font-size: 14px; font-weight: 600; border-radius: 8px; cursor: pointer; }
        .tab-btn.active { background-color: #FF9F0A; color: #121212; }
        
        /* 통계 요약 카드 */
        .stats-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; margin-bottom: 20px; }
        .stat-card { background-color: #1C1C1E; padding: 12px 6px; border-radius: 14px; text-align: center; border: 1px solid #2C2C2E; }
        .stat-card .label { font-size: 11px; color: #8E8E93; margin-bottom: 4px; }
        .stat-card .value { font-size: 15px; font-weight: 700; color: #30D158; }
        
        .calendar-card { background-color: #1C1C1E; border-radius: 16px; padding: 16px; border: 1px solid #2C2C2E; margin-bottom: 24px; }
        
        /* 네비게이터 */
        .month-nav-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
        .nav-btn { background: #2C2C2E; border: 1px solid #3A3A3C; color: #FFFFFF; padding: 5px 10px; border-radius: 8px; font-size: 13px; cursor: pointer; }
        .date-select-group { display: flex; gap: 6px; }
        .select-box { background: #2C2C2E; color: #FFFFFF; border: 1px solid #3A3A3C; padding: 4px 6px; border-radius: 8px; font-size: 14px; font-weight: 600; outline: none; }
        
        /* 주간 뷰 */
        .weekly-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 6px; }
        .week-day-cell {
            background-color: #242426;
            border-radius: 10px;
            padding: 8px 2px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 4px;
            height: 68px;
            cursor: pointer;
        }
        .week-day-name { font-size: 11px; color: #8E8E93; font-weight: 600; }
        .week-day-date { font-size: 13px; font-weight: 700; }
        .week-day-time { font-size: 10px; font-weight: 700; color: #FF9F0A; text-align: center; }

        /* 월간 뷰 */
        .weekdays { display: grid; grid-template-columns: repeat(7, 1fr); text-align: center; font-size: 12px; color: #8E8E93; margin-bottom: 8px; font-weight: 600; }
        .days-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 6px; }
        .day-cell {
            aspect-ratio: 1 / 1;
            background-color: #242426;
            border-radius: 8px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            position: relative;
        }
        .day-cell:active { transform: scale(0.95); }
        .day-cell.empty { background-color: transparent; cursor: default; }
        .day-cell.today { border: 1.5px solid #0A84FF; }
        .day-num { font-size: 11px; font-weight: 600; margin-bottom: 2px; }
        .day-time { font-size: 9px; font-weight: 700; color: #FFFFFF; line-height: 1; }

        .level-1 { background-color: rgba(255, 159, 10, 0.25) !important; color: #FFD60A; }
        .level-2 { background-color: rgba(255, 159, 10, 0.55) !important; color: #FFFFFF; }
        .level-3 { background-color: #FF9F0A !important; color: #121212 !important; }
        .level-3 .day-time { color: #121212; }

        .section-title { font-size: 15px; font-weight: 600; margin-bottom: 12px; color: #E5E5EA; }
        .log-list { display: flex; flex-direction: column; gap: 10px; }
        .log-item { background-color: #1C1C1E; padding: 14px 16px; border-radius: 12px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #2C2C2E; }
        .log-date { font-weight: 600; font-size: 14px; margin-bottom: 2px; }
        .log-time { font-size: 12px; color: #8E8E93; }
        .log-right { display: flex; align-items: center; gap: 10px; }
        .log-duration { font-size: 15px; font-weight: 700; color: #FF9F0A; }
        .delete-btn { background-color: #3A1D1D; color: #FF453A; border: 1px solid #5A2727; padding: 5px 9px; font-size: 11px; border-radius: 6px; cursor: pointer; font-weight: 600; }
        .empty-log { text-align: center; color: #636366; padding: 20px 0; font-size: 13px; }

        /* 바텀시트 모달 */
        .modal-overlay {
            position: fixed;
            top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.65);
            backdrop-filter: blur(4px);
            z-index: 1000;
            display: none;
            align-items: flex-end;
        }
        .modal-content {
            background-color: #1C1C1E;
            width: 100%;
            max-height: 80vh;
            border-top-left-radius: 20px;
            border-top-right-radius: 20px;
            padding: 20px 18px 36px 18px;
            overflow-y: auto;
            border-top: 1px solid #3A3A3C;
            animation: slideUp 0.25s ease-out;
        }
        @keyframes slideUp {
            from { transform: translateY(100%); }
            to { transform: translateY(0); }
        }
        .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
        .modal-title { font-size: 17px; font-weight: 700; color: #FFFFFF; }
        .close-btn { background: none; border: none; font-size: 20px; color: #8E8E93; cursor: pointer; padding: 4px; }
        
        .modal-session-card { background-color: #242426; border-radius: 12px; padding: 14px; margin-bottom: 12px; }
        .modal-session-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
        .modal-time-range { font-size: 13px; color: #8E8E93; }
        .modal-duration { font-size: 15px; font-weight: 700; color: #FF9F0A; }

        .part-chip-group { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
        .part-chip {
            background-color: #2C2C2E;
            color: #8E8E93;
            border: 1px solid #3A3A3C;
            padding: 5px 12px;
            font-size: 12px;
            border-radius: 14px;
            cursor: pointer;
            font-weight: 500;
        }
        .part-chip.selected {
            background-color: #FF9F0A;
            color: #121212;
            border-color: #FF9F0A;
            font-weight: 700;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔥 운동 통계</h1>
        <button class="refresh-btn" onclick="window.location.reload();">🔄 새로고침</button>
    </div>

    <div class="tab-bar">
        <button id="tab-week" class="tab-btn active" onclick="switchTab('week')">주간</button>
        <button id="tab-month" class="tab-btn" onclick="switchTab('month')">월간</button>
    </div>

    <!-- 통계 카드 -->
    <div class="stats-grid">
        <div class="stat-card">
            <div class="label">이번 주 운동</div>
            <div class="value">{{ weekly_total }}</div>
        </div>
        <div class="stat-card">
            <div class="label">이달 출석 일수</div>
            <div class="value" style="color: #FF9F0A;">{{ monthly_days }}일 출석</div>
        </div>
        <div class="stat-card">
            <div class="label">이달 총 운동</div>
            <div class="value">{{ monthly_total }}</div>
        </div>
    </div>

    <!-- 주간 뷰 -->
    <div id="view-week" class="calendar-card">
        <div class="month-nav-bar">
            <span style="font-weight:700;">이번 주 현황</span>
            <span style="font-size:12px; color:#8E8E93;">{{ week_range_str }}</span>
        </div>
        <div class="weekly-grid">
            {% for d in week_days %}
            <div class="week-day-cell {% if d.level > 0 %}level-{{ d.level }}{% endif %} {% if d.is_today %}today{% endif %}"
                 onclick="openDetailModal('{{ d.date_str }}')">
                <span class="week-day-name">{{ d.day_name }}</span>
                <span class="week-day-date">{{ d.day_num }}</span>
                <span class="week-day-time">{{ d.time_str if d.time_str else '-' }}</span>
            </div>
            {% endfor %}
        </div>
    </div>

    <!-- 월간 뷰 -->
    <div id="view-month" class="calendar-card" style="display: none;">
        <div class="month-nav-bar">
            <button class="nav-btn" onclick="navigateMonth({{ prev_year }}, {{ prev_month }})">◀</button>
            <div class="date-select-group">
                <select id="select-year" class="select-box" onchange="jumpToMonth()">
                    {% for y in range(current_year - 3, current_year + 3) %}
                    <option value="{{ y }}" {% if y == target_year %}selected{% endif %}>{{ y }}년</option>
                    {% endfor %}
                </select>
                <select id="select-month" class="select-box" onchange="jumpToMonth()">
                    {% for m in range(1, 13) %}
                    <option value="{{ m }}" {% if m == target_month %}selected{% endif %}>{{ m }}월</option>
                    {% endfor %}
                </select>
            </div>
            <button class="nav-btn" onclick="navigateMonth({{ next_year }}, {{ next_month }})">▶</button>
        </div>
        <div class="weekdays">
            <span>일</span><span>월</span><span>화</span><span>수</span><span>목</span><span>금</span><span>토</span>
        </div>
        <div class="days-grid">
            {% for item in month_calendar %}
                {% if item.day == 0 %}
                    <div class="day-cell empty"></div>
                {% else %}
                    <div class="day-cell {% if item.level > 0 %}level-{{ item.level }}{% endif %} {% if item.is_today %}today{% endif %}"
                         onclick="openDetailModal('{{ item.date_str }}')">
                        <span class="day-num">{{ item.day }}</span>
                        {% if item.time_str %}
                            <span class="day-time">{{ item.time_str }}</span>
                        {% endif %}
                    </div>
                {% endif %}
            {% endfor %}
        </div>
    </div>

    <!-- 최근 운동 내역 목록 -->
    <div class="section-title">최근 운동 내역</div>
    <div class="log-list">
        {% if logs %}
            {% for log in logs %}
            <div class="log-item">
                <div onclick="openDetailModal('{{ log[1] }}')" style="cursor:pointer; flex: 1;">
                    <div class="log-date">{{ log[1] }}</div>
                    <div class="log-time">
                        {{ log[2] }} ~ {{ log[3] }}<span id="log-part-text-{{ log[0] }}">{% if log[6] %} • {{ log[6] }}{% endif %}</span>
                    </div>
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

    <!-- 날짜 세부정보 바텀시트 모달 -->
    <div id="detail-modal" class="modal-overlay" onclick="closeModal(event)">
        <div class="modal-content" onclick="event.stopPropagation()">
            <div class="modal-header">
                <div class="modal-title" id="modal-date-title">운동 기록</div>
                <button class="close-btn" onclick="closeModalDirect()">✕</button>
            </div>
            <div id="modal-body-list"></div>
        </div>
    </div>

    <script>
        const allLogs = {{ logs_json|safe }};
        const bodyPartsList = ['가슴', '등', '하체', '어깨', '삼두', '이두', '복근', '유산소'];

        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('tab') === 'month') {
            switchTab('month');
        }

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

        function navigateMonth(year, month) {
            window.location.href = `/?year=${year}&month=${month}&tab=month`;
        }

        function jumpToMonth() {
            const y = document.getElementById('select-year').value;
            const m = document.getElementById('select-month').value;
            window.location.href = `/?year=${y}&month=${m}&tab=month`;
        }

        function openDetailModal(dateStr) {
            if (!dateStr) return;
            const modal = document.getElementById('detail-modal');
            const title = document.getElementById('modal-date-title');
            const bodyList = document.getElementById('modal-body-list');

            title.textContent = `📅 ${dateStr} 운동 세부기록`;
            bodyList.innerHTML = '';

            const dayLogs = allLogs.filter(item => item.date === dateStr);

            if (dayLogs.length === 0) {
                bodyList.innerHTML = '<div style="color:#8E8E93; text-align:center; padding:24px 0;">해당 날짜의 운동 기록이 없습니다.</div>';
            } else {
                dayLogs.forEach(log => {
                    const card = document.createElement('div');
                    card.className = 'modal-session-card';

                    const currentParts = log.body_part ? log.body_part.split(', ') : [];

                    let chipsHtml = '';
                    bodyPartsList.forEach(part => {
                        const isSel = currentParts.includes(part);
                        chipsHtml += `<span class="part-chip ${isSel ? 'selected' : ''}" onclick="toggleModalPart(${log.id}, '${part}', this)">${part}</span>`;
                    });

                    card.innerHTML = `
                        <div class="modal-session-top">
                            <span class="modal-time-range">${log.start_time} ~ ${log.end_time}</span>
                            <span class="modal-duration">${log.duration}</span>
                        </div>
                        <div style="font-size:12px; color:#8E8E93; margin-bottom:4px;">운동 부위 선택</div>
                        <div class="part-chip-group">${chipsHtml}</div>
                    `;
                    bodyList.appendChild(card);
                });
            }

            modal.style.display = 'flex';
        }

        function closeModal(e) { document.getElementById('detail-modal').style.display = 'none'; }
        function closeModalDirect() { document.getElementById('detail-modal').style.display = 'none'; }

        // 부위 토글 및 최근 내역 텍스트 실시간 반영
        function toggleModalPart(logId, partName, element) {
            const isSelected = element.classList.contains('selected');
            const action = isSelected ? 'remove' : 'add';

            element.classList.toggle('selected');

            fetch(`/gym/update-part/${logId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ part: partName, action: action })
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success') {
                    // 1. 메모리 객체 업데이트
                    const target = allLogs.find(l => l.id === logId);
                    if (target) target.body_part = data.body_part;

                    // 2. 화면 아래 '최근 운동 내역' 행 텍스트 즉시 변경 (새로고침 불필요)
                    const logPartSpan = document.getElementById(`log-part-text-${logId}`);
                    if (logPartSpan) {
                        logPartSpan.textContent = data.body_part ? ` • ${data.body_part}` : '';
                    }
                } else {
                    element.classList.toggle('selected');
                }
            })
            .catch(() => {
                element.classList.toggle('selected');
            });
        }

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
    if not mins: return ""
    h = mins // 60
    m = mins % 60
    if h > 0 and m > 0: return f"{h}h {m}m"
    elif h > 0: return f"{h}h"
    else: return f"{m}m"

def format_minutes_long(mins):
    if not mins: return "0분"
    h = mins // 60
    m = mins % 60
    if h > 0 and m > 0: return f"{h}시간 {m}분"
    elif h > 0: return f"{h}시간"
    else: return f"{m}분"

def get_heat_level(mins):
    if mins <= 0: return 0
    if mins < 45: return 1
    elif mins < 90: return 2
    else: return 3

@app.route("/", methods=["GET"])
def dashboard():
    now_kst = datetime.now(KST)
    today_str = now_kst.strftime("%Y-%m-%d")

    target_year = request.args.get("year", default=now_kst.year, type=int)
    target_month = request.args.get("month", default=now_kst.month, type=int)

    if target_month == 1:
        prev_year = target_year - 1
        prev_month = 12
    else:
        prev_year = target_year
        prev_month = target_month - 1

    if target_month == 12:
        next_year = target_year + 1
        next_month = 1
    else:
        next_year = target_year
        next_month = target_month + 1

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, date, start_time, end_time, duration, duration_minutes, COALESCE(body_part, '') FROM gym_logs ORDER BY id DESC")
    logs = cursor.fetchall()

    logs_json = []
    date_minutes_map = {}
    for log in logs:
        d = log[1]
        date_minutes_map[d] = date_minutes_map.get(d, 0) + (log[5] or 0)
        logs_json.append({
            "id": log[0],
            "date": log[1],
            "start_time": log[2],
            "end_time": log[3],
            "duration": log[4],
            "duration_minutes": log[5],
            "body_part": log[6]
        })

    # 주간 데이터 계산
    monday = now_kst - timedelta(days=now_kst.weekday())
    sunday = monday + timedelta(days=6)
    week_range_str = f"{monday.strftime('%m/%d')} ~ {sunday.strftime('%m/%d')}"
    
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
            "date_str": day_str,
            "time_str": format_minutes_short(m),
            "level": get_heat_level(m),
            "is_today": (day_str == today_str)
        })

    # 월간 데이터 및 순수 출석 일수 계산
    cal = calendar.Calendar(firstweekday=6)
    month_calendar = []
    monthly_total_minutes = 0
    active_days_set = set()

    for date_obj in cal.itermonthdates(target_year, target_month):
        if date_obj.month != target_month:
            month_calendar.append({"day": 0, "date_str": ""})
        else:
            d_str = date_obj.strftime("%Y-%m-%d")
            m = date_minutes_map.get(d_str, 0)
            if m > 0:
                monthly_total_minutes += m
                active_days_set.add(d_str)

            month_calendar.append({
                "day": date_obj.day,
                "date_str": d_str,
                "time_str": format_minutes_short(m),
                "level": get_heat_level(m),
                "is_today": (d_str == today_str)
            })

    cursor.close()
    conn.close()

    return render_template_string(
        HTML_TEMPLATE,
        logs=logs,
        logs_json=json.dumps(logs_json),
        weekly_total=format_minutes_long(weekly_total_minutes),
        monthly_total=format_minutes_long(monthly_total_minutes),
        monthly_days=len(active_days_set),
        week_days=week_days,
        week_range_str=week_range_str,
        month_calendar=month_calendar,
        target_year=target_year,
        target_month=target_month,
        current_year=now_kst.year,
        prev_year=prev_year,
        prev_month=prev_month,
        next_year=next_year,
        next_month=next_month
    )

@app.route("/gym/update-part/<int:log_id>", methods=["POST"])
def update_body_part(log_id):
    data = request.get_json() or {}
    part = data.get("part")
    action = data.get("action")

    conn = get_db_connection()
    cursor = conn.cursor()

    if DATABASE_URL:
        cursor.execute("SELECT COALESCE(body_part, '') FROM gym_logs WHERE id = %s", (log_id,))
    else:
        cursor.execute("SELECT COALESCE(body_part, '') FROM gym_logs WHERE id = ?", (log_id,))
    
    row = cursor.fetchone()
    if not row:
        cursor.close()
        conn.close()
        return jsonify({"status": "not found"}), 404

    current_parts = [p.strip() for p in row[0].split(", ") if p.strip()]

    if action == "add" and part not in current_parts:
        current_parts.append(part)
    elif action == "remove" and part in current_parts:
        current_parts.remove(part)

    updated_str = ", ".join(current_parts)

    if DATABASE_URL:
        cursor.execute("UPDATE gym_logs SET body_part = %s WHERE id = %s", (updated_str, log_id))
    else:
        cursor.execute("UPDATE gym_logs SET body_part = ? WHERE id = ?", (updated_str, log_id))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"status": "success", "body_part": updated_str}), 200

@app.route("/gym/delete/<int:log_id>", methods=["POST"])
def delete_log(log_id):
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
    global start_time
    start_time = datetime.now(KST)
    now_str = start_time.strftime("%H시 %M분")

    msg = f"🏋️ [운동 시작]\n도착 시간: {now_str}\n오늘도 득근하세요!"
    send_telegram(msg)
    return jsonify({"status": "started", "time": now_str}), 200

@app.route("/gym/exit", methods=["POST"])
def exit_gym():
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
            cursor.execute("""
                INSERT INTO gym_logs (date, start_time, end_time, duration, duration_minutes, body_part)
                VALUES (%s, %s, %s, %s, %s, '')
            """, (date_str, start_str, end_str, time_text, duration_minutes))
        else:
            cursor.execute("""
                INSERT INTO gym_logs (date, start_time, end_time, duration, duration_minutes, body_part)
                VALUES (?, ?, ?, ?, ?, '')
            """, (date_str, start_str, end_str, time_text, duration_minutes))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"DB 저장 에러: {e}")

    msg = f"🏆 [운동 완료]\n총 소요 시간: {time_text}\n웹앱에서 운동 부위를 기록해보세요!"
    send_telegram(msg)

    start_time = None
    return jsonify({"status": "finished", "duration": time_text, "date": date_str}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
