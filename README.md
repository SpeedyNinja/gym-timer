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
'''

## 2. 핵심 엔지니어링 의사결정 (Engineering Trade-offs & Deep Dive)

<details open>
<summary><b>🔍 4대 주요 기술적 의사결정 및 트러블슈팅 내역 (펼치기/접기)</b></summary>

<br>

> **1. 클라이언트 인터페이스: 네이티브 앱 대신 'iOS 단축어 + 웹훅' 채택**
> * **배경 & 문제:** 백그라운드 위치 추적 앱(iOS Native/Flutter) 직접 빌드 시 상시 GPS 구동으로 인한 배터리 누수 및 iOS Background Termination Policy로 프로세스 강제 종료.
> * **해결책:** OS 레벨에서 최적화된 iOS 단축어 지오펜싱을 채택해 경계 진입/이탈 순간에만 초경량 웹훅을 전송, 배터리와 클라이언트 리소스 소모 제로화.

---

> **2. 상태 관리 & 데이터 무결성: 인메모리 세션에서 DB 영속화로 전환**
> * **배경 & 문제:** 초기 전역 변수(start_time) 관리 방식은 PaaS 무응답 절전(Spin-down) 및 재배포 시 메모리가 초기화되어 "시작 기록 없음" 런타임 에러 발생.
> * **해결책:** 세션 상태를 DB(gym_logs/active_session)에 직접 영속화. 서버 재시작 후에도 직전 유효 세션을 조회해 오차 없는 운동 시간 계산 보장.

---

> **3. 인프라 & 스토리지: Ephemeral Container 환경의 데이터 유실 해결**
> * **배경 & 문제:** 초기 SQLite(gym_records.db) 파일이 Render 무료 컨테이너의 휘발성 파일 시스템(Ephemeral File System) 특성으로 인해 재배포 시 통째로 삭제.
> * **해결책:** 독립된 클라우드 관리형 PostgreSQL로 즉각 마이그레이션 및 DATABASE_URL 환경 변수 주입을 통해 컨테이너 라이프사이클과 데이터 격리.

---

> **4. 프론트엔드 인터랙션: PWA 최적화 및 비동기 상태 동기화**
> * **UX 최적화:** iOS 홈 화면 웹앱(PWA)의 새로고침 불가 한계를 해결하기 위해 터치 이벤트 기반 Pull-to-refresh 구현.
> * **비동기 태깅:** 운동 부위 선택 칩 클릭 시 페이지 리로드 없이 Fetch API 비동기 통신을 처리하여 모바일 네이티브급 반응 속도 확보.

</details>
