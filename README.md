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
```

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

## 3. 기술 스택 (Tech Stack)

| 구분 | 기술 스택 | 선정 이유 |
| :--- | :--- | :--- |
| **Backend** | `Python`, `Flask`, `Gunicorn` | 경량 웹훅 수신에 특화된 빠른 응답성 및 안정적인 WSGI 서빙 |
| **Database** | `PostgreSQL`, `Psycopg2` | 컨테이너 재배포 시에도 안전한 영속성 제공 및 인덱싱/집계 용이성 |
| **Frontend** | `Vanilla JS`, `Jinja2`, `CSS Grid` | 프레임워크 오버헤드 없는 네이티브 수준의 모바일 다크모드 대시보드 |
| **Infrastructure** | `Render` (Cloud Web Service & DB) | CI/CD 파이프라인 자동화 및 클라우드 인프라 구축 |
| **Automation** | `iOS Shortcuts` (Geofencing), `Telegram Bot API` | OS 단 지오펜싱 이벤트 트리거 및 실시간 푸시 채널 확보 |


## 4. 💡 회고 및 엔지니어링 인사이트 (Retrospective & Insights)

### 1. 헬스 타이머 라이프사이클과 DBeaver를 통한 데이터 영속성 직접 검증
* **타이머 비즈니스 로직과 실제 DB 상태 매핑**: 이번 프로젝트는 단순히 정적인 데이터를 입력하는 것이 아니라, 운동 시작 시각을 기록하고 종료 시점에 소요 시간(`duration_minutes`, `duration`)을 계산하여 누적하는 **'헬스 시간 타이머'** 앱임[cite: 1, 2]. 웹 UI 화면이나 텔레그램 알림 메시지만 바라보는 데 그치지 않고, DBeaver 뷰어 프로그램을 PostgreSQL 인스턴스에 외부 연결하여 실제 테이블(`active_session`, `gym_logs`) 레벨에서 세션이 어떻게 관리되는지 직접 눈으로 확인했음[cite: 1, 2].
* **세션 관리와 트랜잭션 흐름 체감**: 운동 시작 시(`/gym/enter`) 임시 세션 테이블에 시작 시각이 먼저 기록되고, 운동 종료 시(`/gym/exit`) 해당 시작 시간을 꺼내 최종 경과 시간을 계산한 뒤 정규 기록 테이블(`gym_logs`)로 한 행이 안전하게 `INSERT`되는 과정을 DBeaver를 통해 데이터 행 단위로 추적하며 DB 기반 상태 관리(Persistence)의 동작 메커니즘을 확실히 파악했음[cite: 2].
* **'데이터베이스 이해와 활용' 이론의 현실 적용**: 수업과 교재로만 접했던 RDBMS의 2차원 테이블 설계, 행(Row)과 열(Column)의 데이터 타입(`VARCHAR`, `INT`, `TIMESTAMP`), 그리고 고유 식별자인 `SERIAL PRIMARY KEY`의 자동 증가(Auto Increment) 규칙을 DBeaver 스프레드시트 뷰로 검증함[cite: 1, 2]. 특정 운동 기록을 삭제해도 PK 번호가 당겨지지 않고 빈자리로 남아 무결성을 유지하는 등 교과서 속 개념들을 실제 살아있는 데이터로 마주할 수 있어 뜻깊었음[cite: 1, 2].

### 2. 표준시(UTC)와 로컬 타임존(KST) 핸들링의 중요성
* **타이머 앱에서 발견한 9시간 시차**: DBeaver로 데이터를 살펴보던 중, 운동 종료 버튼을 눌러 레코드가 생성된 시각인 `created_at` 컬럼(`CURRENT_TIMESTAMP`)이 한국 현지 시간(KST)보다 정확히 9시간 느린 세계 표준시(UTC)로 적재되고 있음을 발견했음.
* **시간 정합성 분리 기준 확립**: 클라우드 DB 엔진 차원의 타임스탬프(영국 그리니치 기준 UTC)와 앱 서비스 로직(KST 포맷팅 문자열 `start_time`, `end_time`) 간의 기준 차이를 인지하고, 시간 계산 로직을 다룰 때 타임존 정합성을 엄격히 통제해야만 타이머 앱의 데이터 왜곡을 방지할 수 있음을 실습을 통해 깊이 깨달았음.

### 3. 정밀 데이터 로깅과 엔터프라이즈 아키텍처 확장 고민
* **마이크로초 단위의 정밀성**: 타이머 앱의 특성상 정확한 시간 로깅이 생명인데, PostgreSQL의 `TIMESTAMP` 타입이 마이크로초($10^{-6}$초) 단위까지 정밀하게 시간을 추적하여 수동 입력이나 단순 시계 앱보다 훨씬 정밀하고 신뢰도 높은 데이터를 축적할 수 있음을 DBeaver에서 확인함.
* **대규모 상용 서비스 관점의 시야 확장**: 현재는 개인용 헬스 타이머이지만, 수많은 유저가 동시 접속하는 상용 피트니스 플랫폼이나 이커머스 서비스였다면 일반 운동 기록 외에 개인정보 단방향/양방향 암호화(SHA-256, AES-256), 유저-세션-기록 간 외래키(FK) 정규화, 그리고 실시간 타이머 조회를 위한 Redis 인메모리 캐시 도입이 필수적이라는 점까지 엔지니어링 관점의 시야를 넓힐 수 있었음.
