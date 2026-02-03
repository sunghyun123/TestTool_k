# Mobile Device Performance Monitor (AOS / iOS) – QA Internal Tool

Android(AOS) / iOS 실기기에서 특정 앱(패키지/번들)을 선택한 뒤  
**FPS / CPU / GPU(안드로이드) / Memory / Temperature** 지표를 1초 단위로 수집해
GUI 로그로 실시간 확인하는 QA 성능 모니터링 툴입니다.

이 툴은 “성능 테스트 중 체감되는 증상(FPS 드랍, 발열, 메모리 상승)”을
**수치로 빠르게 확인하고 로그로 남기기 위한 목적**으로 제작했습니다.

---

## 핵심 기능

### 1) 공통
- 연결된 디바이스 목록 조회 (AOS 우선, AOS가 연결되면 iOS 목록은 비움)
- 디바이스 선택 후 설치 앱(패키지/번들) 목록 조회 및 선택
- 1초 주기 성능 수집 및 GUI에 실시간 로그 출력
- Stop 이벤트 기반 스레드 종료(수집 중단)

### 2) Android(AOS)
- FPS: `SurfaceFlinger --latency` 기반 프레임 타임스탬프를 수집해 FPS 계산
- CPU / Memory: `top` 출력 기반 추출 및 전체 코어/전체 메모리 대비 퍼센트로 정규화
- GPU: 디바이스별 노출 경로 차이를 고려해 2가지 경로 시도  
  - `kgsl gpu_busy_percentage` → 실패 시 `mali utilization`
- Temperature: `dumpsys battery` 기반 추출(1/10°C 단위)

### 3) iOS (iOS 17+ 포함)
- 디바이스/앱 정보: `tidevice info`, `tidevice applist`, `tidevice appinfo`
- FPS: `pymobiledevice3 developer dvt graphics` 출력에서 JSON 형태 데이터 파싱
- CPU / physFootprint: `pymobiledevice3 developer dvt sysmon process single` JSON 파싱
- Temperature: `pymobiledevice3 diagnostics battery single` JSON 파싱
- iOS 17+ : 원격 터널(`start-tunnel`)을 먼저 열고 `--rsd host port` 기반으로 dvt 명령 실행

> 참고: iOS 메모리는 기기 모델별 RAM 테이블을 유지하고, 수집한 physFootprint를
> “전체 RAM 대비 %”로 변환합니다. (신규 기기 추가 시 테이블 업데이트 필요)

---

## 실행 환경 / 요구사항

### OS
- macOS / Windows 모두 가능 (단, iOS 도구 설치/연결은 환경 영향을 많이 받음)

### 필수 도구
- Android:
  - `adb` (Android Platform Tools)
- iOS:
  - `tidevice`
  - `pymobiledevice3`
  - iOS 17+에서 `sudo pymobiledevice3 remote start-tunnel` 권한 필요할 수 있음

### Python 패키지
- 표준 라이브러리: `tkinter`, `subprocess`, `threading`, `re`, `json`, `time`
- 추가 pip 설치는 iOS 도구(`pymobiledevice3`) 중심으로 필요

---
### 🔹 사용 기술

- Python
- Tkinter (GUI)
- subprocess / threading / queue
- Android Debug Bridge (adb)
- tidevice
- pymobiledevice3
- iOS DVT(Graphics / Sysmon / Diagnostics)
- Regular Expression (re)
- JSON Parsing
