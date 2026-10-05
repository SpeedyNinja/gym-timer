# 🏋️ GymTimer: Geofence-driven Fitness Automation

> **iOS 단축어 기반 지오펜싱(Geofencing)과 클라우드 백엔드를 연동해 수동 입력 없이 운동 세션을 자동 로깅하고 시각화하는 풀스택 자동화 서비스**

---

## 1. 아키텍처 다이어그램 (Architecture)

```text
[ iOS Shortcut ]
   ├── (도착) Geofence Trigger ──────> POST /gym/enter ──┐
   └── (이탈) Geofence Trigger ──────> POST /gym/exit ───┼─> [ Render Flask App (Gunicorn) ]
                                                          │          │ (KST Session Engine)
[ Safari / PWA Dashboard ]                                │          ▼
   ├── Dynamic Heatmap / Calendar ───> GET / ────────────┤   [ PostgreSQL (gym-db) ]
   └── Async Body Part Tagging ──────> POST /gym/update ─┘           │
                                                                     ▼
                                                          [ Telegram Bot API ]
                                                                     │
                                                                     ▼
                                                          (실시간 시작/완료 푸시 알림)
