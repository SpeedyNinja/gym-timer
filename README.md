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

### 1. DBeaver 실습을 통한 '데이터베이스 이해와 활용' 체감
* **이론에서 실제로, 원본 데이터 검증**: 웹 대시보드 화면 너머 백엔드에서 실제로 어떤 일이 일어나는지 DBeaver를 통해 직접 확인함. 교재나 강의로만 접했던 RDBMS의 2차원 테이블(`gym_logs`) 구조와 행(Row)·열(Column)에 실제 운동 기록(`start_time`, `end_time`, `duration_minutes`, `body_part` 등)이 의도한 데이터 규격대로 정합성을 유지하며 적재되는 모습을 눈으로 확인하며 데이터 모델링과 영속화의 의미를 실감했음.
* **PK(Primary Key)와 SERIAL 메커니즘 확인**: 레코드가 쌓일 때마다 1씩 증가하는 `SERIAL PRIMARY KEY`의 자동 증가(Auto Increment) 동작과, 특정 데이터를 삭제했을 때 번호가 당겨지지 않고 고유 식별자로서 빈자리를 유지하는 DB 기본 무결성 보장 원리를 실제 데이터를 보며 확실히 이해했음.

### 2. 표준시(UTC)와 로컬 타임존(KST) 핸들링의 중요성
* **시차를 직접 보며 배운 교훈**: `created_at` 컬럼의 기본값(`CURRENT_TIMESTAMP`)이 영국 그리니치 표준시(UTC) 기준으로 적재되어 한국 시간(KST)과 9시간 차이가 발생하는 현상을 DBeaver로 직접 발견함.
* **타임존 분리의 필요성**: 클라우드 인프라 레벨의 기본 타임스탬프(UTC)와 애플리케이션 비즈니스 로직(KST 포맷팅) 간의 기준점을 명확히 분리하고 동기화해야 데이터 왜곡을 방지할 수 있음을 실습을 통해 체득했음.

### 3. 정밀 데이터 로깅과 엔터프라이즈 아키텍처 확장 고민
* **정밀한 타임스탬프**: DB 엔진이 밀리초·마이크로초 단위까지 정밀하게 시간을 추적하여 수동 입력 방식보다 훨씬 신뢰성 높은 데이터를 남길 수 있음을 확인했음.
* **실무 보안 및 확장성에 대한 시야 확장**: 대규모 상용 서비스(이커머스 등) 관점이라면 운동 기록 같은 일반 데이터와 달리 회원 정보나 결제 내역은 평문 저장이 아닌 단방향/양방향 암호화(SHA-256, AES-256) 처리, 정규화된 테이블 분리, Redis 같은 초고속 캐시 계층 도입이 필수적이라는 점까지 엔지니어링 시야를 넓힐 수 있었음.
