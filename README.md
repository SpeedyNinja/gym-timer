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
2. 핵심 엔지니어링 의사결정 (Engineering Trade-offs & Deep Dive)📌 1) 클라이언트 인터페이스: 네이티브 앱 대신 'iOS 단축어 + 웹훅' 채택배경 & 문제: 백그라운드 위치 추적 앱(iOS Native/Flutter)을 직접 빌드할 경우 상시 GPS 구동으로 인한 심각한 배터리 소모와 iOS Background Termination Policy로 인해 프로세스가 강제 종료되는 한계가 존재했습니다.해결책: OS 레벨에서 효율적으로 최적화된 iOS 단축어의 지오펜싱 트리거를 활용했습니다. 경계 진입/이탈 순간에만 백엔드로 초경량 웹훅(HTTP POST)을 발송하도록 설계하여 배터리 소모와 클라이언트 유지 비용을 제로화했습니다.📌 2) 상태 관리 & 데이터 무결성: 인메모리 세션에서 DB 영속화로 전환배경 & 문제: 초기 버전에서는 시작 시각을 전역 변수(start_time)에 보관했으나, PaaS 특성상 무응답 시 인스턴스가 절전(Spin-down)되거나 깃허브 커밋 재배포 시 컨테이너가 교체되면서 메모리가 초기화되어 "시작 기록이 없습니다" 에러가 발생했습니다.해결책:세션 상태를 메모리가 아닌 DB(gym_logs / active_session)에 영속화했습니다.서버가 꺼지거나 재부팅되어도 종료 요청 시 DB의 직전 유효 세션을 조회해 오차 없이 운동 시간을 계산하도록 복원력을 확보했습니다.📌 3) 인프라 & 스토리지: Ephemeral Container 환경의 데이터 유실 해결배경 & 문제: 초기에 파일 기반 SQLite(gym_records.db)를 사용했으나, Render 무료 컨테이너 환경의 휘발성 파일 시스템(Ephemeral File System) 특성으로 인해 재배포 및 인스턴스 재시작 시 DB 파일 자체가 영구 삭제되는 문제가 발생했습니다.해결책:데이터베이스 레이어를 독립된 클라우드 관리형 RDBMS인 PostgreSQL로 즉각 마이그레이션했습니다.내부 네트워크 통신망(Internal Database URL) 및 환경 변수(DATABASE_URL)를 주입해 컨테이너 라이프사이클과 무관하게 데이터 영속성을 100% 보장했습니다.📌 4) 프론트엔드 인터랙션: PWA 최적화 및 비동기 상태 동기화UX 최적화: iOS 홈 화면 웹앱(PWA Web Clip) 환경에서 주소창 제거로 인한 새로고침 불가 문제를 해결하기 위해 터치 이벤트 기반 Pull-to-refresh 및 전용 리프레시 인터페이스를 구축했습니다.비동기 태깅: 운동 부위 선택 칩을 누를 때 전체 뷰를 리로드하지 않고 Fetch API 기반 비동기 PATCH/POST로 처리하여 모바일 환경에서 지연 없는 사용자 경험을 구현했습니다.3. 기술 스택 (Tech Stack)구분기술 스택선정 이유BackendPython, Flask, Gunicorn경량 웹훅 수신에 특화된 빠른 응답성 및 안정적인 WSGI 서빙DatabasePostgreSQL, Psycopg2컨테이너 재배포 시에도 안전한 영속성 제공 및 인덱싱/집계 용이성FrontendVanilla JS, Jinja2, CSS Grid프레임워크 오버헤드 없는 네이티브 수준의 모바일 다크모드 대시보드InfrastructureRender (Cloud Web Service & DB)CI/CD 파이프라인 자동화 및 클라우드 인프라 구축AutomationiOS Shortcuts (Geofencing), Telegram Bot APIOS 단 지오펜싱 이벤트 트리거 및 실시간 푸시 채널 확보4. API 명세 (API Endpoints)MethodEndpointDescriptionPOST/gym/enter헬스장 진입 웹훅 수신, 시작 타임스탬프 DB 기록 및 텔레그램 알림POST/gym/exit헬스장 이탈 웹훅 수신, 소요 시간 계산/기록 및 완료 알림GET/주간/월간 잔디(히트맵) 통계 및 운동 로그 캘린더 대시보드 렌더링POST/gym/update-part/<id>해당 세션의 운동 부위 태그 비동기 토글 갱신POST/gym/delete/<id>특정 운동 기록 레코드 삭제
