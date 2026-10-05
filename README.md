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
## 2. 핵심 엔지니어링 의사결정 (Engineering Trade-offs & Deep Dive)
📌 1) 클라이언트 인터페이스: 네이티브 앱 대신 'iOS 단축어 + 웹훅' 채택
배경 & 문제: 백그라운드 위치 추적 앱(iOS Native/Flutter)을 직접 빌드할 경우 상시 GPS 구동으로 인한 심각한 배터리 소모와 iOS Background Termination Policy로 인해 프로세스가 강제 종료되는 한계가 존재했습니다.

해결책: OS 레벨에서 효율적으로 최적화된 iOS 단축어의 지오펜싱 트리거를 활용했습니다. 경계 진입/이탈 순간에만 백엔드로 초경량 웹훅(HTTP POST)을 발송하도록 설계하여 배터리 소모와 클라이언트 유지 비용을 제로화했습니다.
