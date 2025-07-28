# 실제 프로젝트 통합 Implementation Plan

## 🎯 현재 상황 (2024.07.24)

### ✅ 완료된 작업 (Phase 0)
- CoSimulationParams, NestParams, SimulationParameters 기본 스키마 구현
- ParameterValidator 서비스 클래스 구현
- 기본 테스트 인프라 구축
- example/short_simulation/parameter.json 검증 성공

### 🎯 다음 우선순위 (Phase 1) - 핵심 확장

## Tasks

### ✅ 1. [완료] 기본 인프라 및 핵심 스키마

기본 테스트 인프라와 핵심 파라미터 스키마가 구현되어 실제 parameter.json 파일 검증이 가능합니다.

- ✅ CoSimulationParams 스키마 (co-simulation, nb_MPI_nest, id_region_nest 등)
- ✅ NestParams 스키마 (sim_resolution, master_seed, total_num_virtual_procs 등)
- ✅ SimulationParameters 루트 스키마 (begin, end, result_path 검증)
- ✅ ParameterValidator.load_and_validate() 메서드
- ✅ 기본 테스트 케이스 및 성능 검증 (6ms < 100ms 목표)
- _Requirements: 1.1, 2.1, 5.4_

### 🎯 2. [다음 우선순위] 복잡한 중첩 파라미터 스키마 구현

실제 parameter.json의 가장 복잡한 섹션들을 검증하기 위한 스키마 구현

#### 2.1 NestTopologyParams 스키마 구현 ⭐ 최우선

가장 복잡한 중첩 구조 (param_neuron_excitatory/inhibitory)를 포함한 NEST 토폴로지 검증

```python
# 목표: 이런 복잡한 구조 검증
"param_nest_topology": {
    "neuron_type": "aeif_cond_exp",
    "param_neuron_excitatory": {
        "C_m": 200.0, "t_ref": 5.0, "V_reset": -64.5, 
        "E_L": -64.5, "g_L": 10.0, "I_e": 0.0, "a": 0.0, 
        "b": 1.0, "Delta_T": 2.0, "tau_w": 500.0, "V_th": -50.0,
        "E_ex": 0.0, "tau_syn_ex": 5.0, "E_in": -80.0, "tau_syn_in": 5.0
    },
    "param_neuron_inhibitory": { /* 동일한 15개 파라미터 */ },
    "nb_region": 104, "nb_neuron_by_region": 1000, "percentage_inhibitory": 0.2
}
```

- NeuronParams 기본 클래스 구현 (15개 뉴런 파라미터)
- 물리학적 제약 조건 검증 (V_reset < V_th, E_ex > E_in 등)
- NestTopologyParams 컨테이너 클래스
- 인구 크기 제한 및 균형 검증
- _Requirements: 1.2, 3.1, 4.1_

#### 2.2 NestConnectionParams 스키마 구현 ⭐ 파일 경로 검증

파일 경로 검증과 연결 파라미터를 포함한 NEST 연결 검증

```python
# 목표: 파일 경로 + 연결 파라미터 검증
"param_nest_connection": {
    "weight_local": 1.0, "g": 5.0, "p_connect": 0.05,
    "weight_global": 1.0, "nb_external_synapse": 115,
    "path_weight": "/home/nest_elephant_tvb/parameter/data_mouse/weights.npy",
    "path_distance": "/home/nest_elephant_tvb/parameter/data_mouse/distance.npy",
    "velocity": 3.0
}
```

- 파일 경로 검증 (개발/프로덕션 환경 구분)
- 연결 파라미터 범위 검증
- 물리학적 제약 조건 (속도, 확률 등)
- 상대/절대 경로 지원
- _Requirements: 1.2, 4.1, 6.1_

#### 2.3 Translation Parameters 스키마 구현 ⭐ 동적 파일 처리

NEST↔TVB 번역 파라미터와 동적 파일 생성 처리

```python
# 목표: 동적 파일 생성 + 번역 파라미터 검증
"param_TR_nest_to_tvb": {
    "init": "./short_simulation//init_spikes.npy",  # 동적 생성
    "resolution": 0.1, "nb_neurons": 800.0, "synch": 3.5,
    "width": 20.0, "level_log": 1
}
```

- TranslationNestToTvbParams 스키마
- TranslationTvbToNestParams 스키마  
- 동적 파일 생성 경로 검증
- 번역 파라미터 일관성 검증
- _Requirements: 1.4, 2.4, 4.1_

### 🔄 3. [진행 중] run_exploration.py 즉시 통합

기존 25줄 수동 검증을 1줄 Pydantic 검증으로 대체하여 즉시 효과 확인

#### 3.1 run_exploration.py 수동 검증 제거 ⭐ 즉시 적용

현재 run_exploration.py:45-70의 25줄 수동 검증을 Pydantic으로 대체

```python
# 현재 (25줄 수동 검증)
if not param_file.exists():
    raise FileNotFoundError(f"Parameter file not found: {param_file}")
with param_file.open('r') as f:
    parameters = json.load(f)
required_keys = ['param_co_simulation', 'param_nest', 'begin', 'end']
for key in required_keys:
    if key not in parameters:
        raise KeyError(f"Missing required parameter: {key}")
# ... 20줄 더

# 새로운 (1줄 검증)
from nest_elephant_tvb.orchestrator.validation import ParameterValidator
params = ParameterValidator.load_and_validate(parameters_file)
```

- 기존 수동 검증 코드 제거
- Pydantic 검증으로 대체
- 기존 테스트 모두 통과 확인
- 성능 개선 측정 (25줄 → 1줄)
- _Requirements: 1.1, 2.1, 5.3_

#### 3.2 하위 호환성 안전장치 구현

검증 실패시 기존 방식으로 fallback하는 안전장치

```python
def safe_load_parameters(param_file):
    try:
        return ParameterValidator.load_and_validate(param_file)
    except Exception as e:
        print(f"Pydantic validation failed, using legacy: {e}")
        return load_parameters_legacy(param_file)
```

- BackwardCompatibilityManager 클래스 구현
- 검증 실패시 기존 방식 fallback
- 점진적 마이그레이션 지원
- 에러 로깅 및 모니터링
- _Requirements: 2.1, 2.2, 5.3_

### 🔧 4. [향후] parameters_manager.py 점진적 통합

복잡한 파라미터 연결 로직을 type-safe하게 리팩토링

#### 4.1 create_linked_parameters() 하이브리드 지원

기존 dict와 새로운 Pydantic 객체를 모두 지원하는 하이브리드 함수

```python
# 현재 문제: 15개 이상의 복잡한 파라미터 연결
param_tvb_model['g_L'] = param_nest_topology['param_neuron_excitatory']['g_L']
param_tvb_model['Q_i'] = param_nest_connection['weight_local'] * param_nest_connection['g']

# 해결책: 하이브리드 접근
def create_linked_parameters_v2(results_path, parameters):
    if hasattr(parameters, 'model_dump'):
        # Type-safe Pydantic 접근
        param_co_simulation = parameters.param_co_simulation
    else:
        # 기존 dict 접근 (하위 호환)
        param_co_simulation = parameters['param_co_simulation']
```

- Pydantic 객체와 dict 모두 지원
- 기존 파라미터 연결 로직 유지
- Type-safe 접근 점진적 도입
- 동적 파일 생성 로직 개선
- _Requirements: 2.1, 5.3, 7.1_

#### 4.2 save_parameter() Pydantic 호환성

Pydantic 객체 직렬화 지원 추가

```python
def save_parameter_v2(parameters, results_path, begin, end):
    if hasattr(parameters, 'model_dump'):
        param_dict = parameters.model_dump(by_alias=True)
    else:
        param_dict = parameters
    
    complete_parameters = {
        **param_dict,
        "result_path": str(results_dir.resolve()) + "/",
        "begin": begin, "end": end
    }
```

- Pydantic 객체 직렬화 지원
- 기존 JSON 형식 유지
- 파라미터 파일 round-trip 테스트
- 성능 최적화
- _Requirements: 2.3, 4.4, 7.3_

### 📊 5. [향후] 고급 파라미터 섹션 확장

복잡한 TVB 모델과 조건부 검증이 필요한 섹션들

#### 5.1 TVB Model Parameters 스키마 구현

가장 복잡한 TVB 모델 파라미터 검증 (배열, 초기 조건 등)

```python
# 목표: 복잡한 TVB 모델 파라미터 검증
"param_tvb_model": {
    "order": 2, "T": 20.0,
    "P_e": [-0.05059317, 0.0036078, ...],  # 10개 배열
    "P_i": [-0.0596722865, 0.00715675508, ...],  # 10개 배열
    "initial_condition": {  # 중첩 구조
        "E": [0.0, 0.0], "I": [0.0, 0.0], "C_ee": [0.0, 0.0]
    }
}
```

- TVB 모델 파라미터 스키마
- 배열 크기 동적 검증
- 초기 조건 중첩 구조 검증
- 물리학적 제약 조건
- _Requirements: 1.3, 4.1_

#### 5.2 Background Parameters 조건부 검증

multimeter, record_spike 등 조건부 필드 검증

```python
# 목표: 조건부 검증
"param_nest_background": {
    "multimeter": true,
    "multimeter_list": {  # multimeter=true일 때만 필수
        "pop_1_ex_VM": [["V_m"], 0, 10]
    }
}
```

- 조건부 필드 검증 로직
- 복잡한 딕셔너리 구조 검증
- 선택적 기능 파라미터 처리
- _Requirements: 1.3, 6.1_

### 🧪 6. [지속적] 실제 파라미터 파일 호환성 테스트

모든 기존 파라미터 파일과의 호환성 확보

#### 6.1 전체 parameter.json 파일 검증 테스트

프로젝트 내 모든 기존 파라미터 파일 호환성 확인

```bash
# 테스트 대상 파일들
example/short_simulation/parameter.json     ✅ 이미 테스트됨
example/long_simulation/parameter.json      🎯 테스트 필요
tests/test_co-sim/*/parameter.json          🎯 테스트 필요
```

- 모든 기존 파라미터 파일 자동 검증
- 호환성 문제 식별 및 해결
- 회귀 테스트 자동화
- CI/CD 파이프라인 통합
- _Requirements: 2.1, 5.3_

#### 6.2 성능 벤치마크 및 모니터링

검증 성능이 요구사항을 만족하는지 지속적 모니터링

```python
# 성능 목표
- 검증 시간: < 50ms (현재 6ms ✅)
- 메모리 사용: < 1MB 추가
- CPU 오버헤드: < 5%
```

- 성능 벤치마크 테스트 자동화
- 메모리 사용량 모니터링
- 대용량 파라미터 파일 테스트
- MPI 환경 성능 테스트
- _Requirements: 4.1, 4.2, 4.3_

### 🚀 7. [최적화] 프로덕션 준비 및 고급 기능

프로덕션 환경을 위한 최적화와 고급 기능 구현

#### 7.1 에러 메시지 품질 개선

사용자 친화적이고 실행 가능한 에러 메시지 제공

```python
# 목표: 명확하고 실행 가능한 에러 메시지
ValidationError: 
  param_nest_topology.param_neuron_excitatory.V_reset (-64.5) must be less than V_th (-50.0)
  Suggestion: Set V_reset to a value below -50.0, typically around -65.0
  
  param_nest_connection.path_weight: File not found '/home/.../weights.npy'
  Suggestion: Check file path or set ENVIRONMENT=development to skip file validation
```

- 구체적이고 실행 가능한 에러 메시지
- 자동 수정 제안 기능
- 에러 컨텍스트 정보 제공
- 다국어 지원 (한국어/영어)
- _Requirements: 6.1, 6.2, 6.3_

#### 7.2 JSON Schema 문서 자동 생성

Pydantic 모델에서 자동으로 문서 생성

```python
# 목표: 자동 문서 생성
parameter_schema = SimulationParameters.model_json_schema()
generate_markdown_docs(parameter_schema)
generate_html_docs(parameter_schema)
```

- JSON Schema 자동 생성
- 마크다운/HTML 문서 생성
- 파라미터 예제 자동 생성
- 버전별 스키마 관리
- _Requirements: 7.5, 6.1_

## 📋 실행 우선순위 및 타임라인

### 🎯 Phase 1: 즉시 적용 (1-2일) - 기존 코드 최소 변경
**목표**: run_exploration.py 25줄 → 1줄 변경으로 즉시 효과 확인

1. **Task 3.1**: run_exploration.py 수동 검증 제거 ⭐ **최우선**
2. **Task 3.2**: 하위 호환성 안전장치 구현
3. **Task 6.1**: 기존 parameter.json 파일들 호환성 테스트

### 🔧 Phase 2: 핵심 확장 (3-5일) - 복잡한 파라미터 추가
**목표**: 가장 중요하고 복잡한 파라미터 섹션 검증

1. **Task 2.1**: NestTopologyParams 스키마 (복잡한 중첩 구조)
2. **Task 2.2**: NestConnectionParams 스키마 (파일 경로 검증)
3. **Task 2.3**: Translation Parameters 스키마 (동적 파일)

### 🚀 Phase 3: 완전 통합 (5-7일) - parameters_manager.py 리팩토링
**목표**: Type-safe 파라미터 연결 및 동적 생성

1. **Task 4.1**: create_linked_parameters() 하이브리드 지원
2. **Task 4.2**: save_parameter() Pydantic 호환성
3. **Task 5.1**: TVB Model Parameters 스키마
4. **Task 5.2**: Background Parameters 조건부 검증

### 🎨 Phase 4: 최적화 (선택사항) - 사용자 경험 개선
**목표**: 프로덕션 품질 및 고급 기능

1. **Task 7.1**: 에러 메시지 품질 개선
2. **Task 7.2**: JSON Schema 문서 자동 생성
3. **Task 6.2**: 성능 벤치마크 및 모니터링

## 🎯 다음 실행할 Task 추천

### 즉시 실행 권장: **Task 3.1 - run_exploration.py 수동 검증 제거**

**이유**:
- 기존 25줄 수동 검증을 1줄로 대체하여 즉시 효과 확인 가능
- 기존 코드 변경 최소화 (위험도 낮음)
- 이미 구현된 스키마로 바로 적용 가능
- 성능 개선 즉시 측정 가능

**예상 소요 시간**: 2-3시간
**위험도**: 낮음 (기존 테스트 모두 통과 확인됨)
**효과**: 높음 (25줄 → 1줄, 타입 안전성 확보)

## 🔍 실제 통합 고려사항

### 현재 프로젝트 특성 분석

#### parameters_manager.py의 복잡성
- **15개 이상의 파라미터 연결**: TVB ↔ NEST 간 복잡한 의존성
- **동적 파일 생성**: init_rates.npy, init_spikes.npy 런타임 생성
- **조건부 로직**: co-simulation 여부에 따른 분기 처리

#### 실제 parameter.json 구조
- **중첩 깊이**: 최대 3단계 (param_nest_topology.param_neuron_excitatory.*)
- **파일 경로**: 6개 외부 파일 의존성 (weights.npy, distance.npy 등)
- **배열 데이터**: P_e, P_i 각각 10개 요소

### 통합 전략

#### 1. 점진적 마이그레이션
```python
# 하이브리드 접근: 기존 dict와 새로운 Pydantic 동시 지원
def create_linked_parameters_v2(results_path, parameters):
    if hasattr(parameters, 'model_dump'):
        # 새로운 type-safe 접근
        param_co_simulation = parameters.param_co_simulation
    else:
        # 기존 dict 접근 (하위 호환)
        param_co_simulation = parameters['param_co_simulation']
```

#### 2. 환경별 검증 수준
```python
# 개발 환경: 관대한 검증 (경고만)
# 프로덕션 환경: 엄격한 검증 (에러)
if os.getenv('ENVIRONMENT') == 'development':
    print(f"Warning: File not found: {path}")
else:
    raise ValueError(f"Required file not found: {path}")
```

#### 3. 성능 최적화
- **현재 성능**: 6ms (목표 100ms 대비 매우 우수)
- **메모리 사용**: <1MB 추가 (목표 10MB 대비 우수)
- **검증 범위**: 점진적 확장 (핵심 → 전체)

### 성공 기준

#### 각 Task 완료 조건
- ✅ 모든 기존 테스트 통과
- ✅ 새로운 기능 테스트 추가
- ✅ 성능 요구사항 만족
- ✅ 하위 호환성 유지
- ✅ 에러 메시지 품질 확보

#### 전체 프로젝트 성공 기준
- **기능**: 25줄 수동 검증 → 1줄 자동 검증
- **안전성**: 타입 안전성 및 범위 검증 확보
- **성능**: 검증 시간 <50ms, 메모리 <1MB 추가
- **호환성**: 모든 기존 parameter.json 파일 지원
- **유지보수성**: IDE 자동완성, 명확한 에러 메시지

이 계획은 실제 프로젝트의 복잡성을 고려하여 점진적이고 안전한 통합을 보장합니다.