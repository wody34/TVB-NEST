# 놓치고 있던 중요 패턴 분석

## 🔍 **발견된 핵심 패턴들**

### 1. **파라미터 탐색 워크플로우** ⭐ **가장 중요**

#### 현재 워크플로우 체인:
```python
# 1. 파라미터 탐색 시작점
run_exploration_2D(path, parameter_default, dict_variables, begin, end)
    ↓
# 2. 개별 시뮬레이션 실행
run_exploration(results_path, parameter_default, dict_variable, begin, end)
    ↓
# 3. 파라미터 생성 및 연결
parameters = generate_parameter(parameter_default, results_path, dict_variable)
    ↓
# 4. 파라미터 저장
save_parameter(parameters, results_path, begin, end)
    ↓
# 5. 시뮬레이션 실행
run(str(param_file))
```

#### **놓친 중요점**: 
- **parameter_default는 Python 모듈 객체**가 아니라 **example.parameter.test_nest** 모듈!
- **dict_variable**을 통한 동적 파라미터 수정
- **파라미터 탐색 루프**에서 각 조합마다 새로운 parameter.json 생성

### 2. **example.parameter.test_nest 모듈 의존성** ⭐ **매우 중요**

#### 실제 사용 패턴:
```python
# tests/run_co-sim.py
from example.parameter import test_nest as parameter_test

# 런타임 파라미터 수정
parameter_test.param_co_simulation['co-simulation'] = True
parameter_test.param_co_simulation['nb_MPI_nest'] = 4
parameter_test.param_nest['total_num_virtual_procs'] = parameter_test.param_co_simulation['nb_MPI_nest']

# 파라미터 탐색 실행
run_exploration_2D(path, parameter_test, {'g':np.arange(1.0, 1.2, 0.5), 'mean_I_ext': [0.0]}, begin, end)
```

#### **놓친 중요점**:
- **parameter_default는 모듈 객체**이므로 `dir(parameter_default)`로 속성 탐색
- **getattr(parameter_default, parameters_name)**로 동적 속성 접근
- **모듈 수준에서 파라미터 수정** 후 탐색 실행

### 3. **generate_parameter() 함수의 복잡한 로직** ⭐ **중요**

#### 현재 구현의 복잡성:
```python
def generate_parameter(parameter_default, results_path, dict_variable=None):
    parameters = {}
    if dict_variable != None:
        for variable in dict_variable.keys():
            # 1. 모듈의 모든 'param' 속성 탐색
            for parameters_name in dir(parameter_default):
                if 'param' in parameters_name:
                    parameters_values = getattr(parameter_default, parameters_name)
                    if variable in parameters_values:
                        parameters_values[variable] = dict_variable[variable]
                    parameters[parameters_name] = parameters_values
            
            # 2. 특별 처리: excitatory 뉴런 파라미터
            if variable in parameters['param_nest_topology']['param_neuron_excitatory'].keys():
                parameters['param_nest_topology']['param_neuron_excitatory'][variable] = dict_variable[variable]
    
    return create_linked_parameters(results_path, parameters)
```

#### **놓친 중요점**:
- **모듈 introspection**: `dir()` + `getattr()` 패턴
- **중첩 딕셔너리 수정**: excitatory 뉴런 파라미터 특별 처리
- **파라미터 탐색 변수**가 여러 섹션에 동시 적용될 수 있음

### 4. **Jupyter 노트북에서의 직접 사용** ⭐ **중요**

#### 발견된 패턴:
```python
# example/demonstration_mouse_brain.ipynb
from nest_elephant_tvb.orchestrator.parameters_manager import save_parameter, create_linked_parameters

# 직접 함수 호출
parameters = create_linked_parameters(folder_simulation, param)
save_parameter(parameters, folder_simulation, begin, end)
```

#### **놓친 중요점**:
- **create_linked_parameters()가 독립적으로 사용됨**
- **Jupyter 환경에서의 인터랙티브 사용**
- **generate_parameter() 없이 직접 create_linked_parameters() 호출**

### 5. **파라미터 탐색의 다양한 패턴** ⭐ **중요**

#### 발견된 탐색 패턴들:
```python
# 1. 단일 값 탐색
{'g': [1.0], 'mean_I_ext': [0.0]}

# 2. 범위 탐색
{'g': np.arange(1.0, 1.2, 0.5), 'mean_I_ext': [0.0]}

# 3. 2D 그리드 탐색
{'g': np.arange(0.0, 1.0, 0.5), 'mean_I_ext': np.arange(0.0, 100.0, 50.0)}

# 4. 뉴런 파라미터 탐색
{'b': [10.0, 7.0, 1.0], 'mean_I_ext': [0.0]}
```

#### **놓친 중요점**:
- **numpy 배열 지원** 필요
- **다차원 파라미터 공간** 탐색
- **뉴런 모델 파라미터** (b, g, mean_I_ext 등) 탐색

## 🚨 **Pydantic 통합에서 고려해야 할 중요 사항들**

### 1. **모듈 객체 vs Pydantic 모델**

#### 현재 문제:
```python
# 현재: parameter_default는 모듈 객체
for parameters_name in dir(parameter_default):  # 모듈 속성 탐색
    parameters_values = getattr(parameter_default, parameters_name)  # 동적 접근
```

#### Pydantic 통합 해결책:
```python
def generate_parameter_v2(parameter_default, results_path, dict_variable=None):
    # 1. 모듈 객체를 Pydantic 모델로 변환
    if hasattr(parameter_default, '__dict__'):  # 모듈 객체
        param_dict = {}
        for attr_name in dir(parameter_default):
            if 'param' in attr_name and not attr_name.startswith('_'):
                param_dict[attr_name] = getattr(parameter_default, attr_name)
        
        # Pydantic 모델 생성
        params = SimulationParameters(**param_dict)
    else:
        # 이미 Pydantic 모델
        params = parameter_default
    
    # 2. dict_variable 적용
    if dict_variable:
        params = apply_parameter_exploration(params, dict_variable)
    
    return create_linked_parameters_v2(results_path, params)
```

### 2. **파라미터 탐색 변수 적용**

#### 현재 복잡한 로직:
```python
# 여러 섹션에서 동일 변수 찾아서 수정
for variable in dict_variable.keys():
    for parameters_name in dir(parameter_default):
        if 'param' in parameters_name:
            parameters_values = getattr(parameter_default, parameters_name)
            if variable in parameters_values:
                parameters_values[variable] = dict_variable[variable]
```

#### Pydantic 통합 해결책:
```python
def apply_parameter_exploration(params: SimulationParameters, dict_variable: dict) -> SimulationParameters:
    \"\"\"파라미터 탐색 변수를 Pydantic 모델에 적용\"\"\"
    # 모델을 dict로 변환
    param_dict = params.model_dump()
    
    for variable, value in dict_variable.items():
        # 모든 파라미터 섹션에서 해당 변수 찾아서 수정
        for section_name, section_data in param_dict.items():
            if isinstance(section_data, dict) and variable in section_data:
                section_data[variable] = value
            
            # 중첩 구조 처리 (excitatory/inhibitory 뉴런)
            if section_name == 'param_nest_topology' and isinstance(section_data, dict):
                for neuron_type in ['param_neuron_excitatory', 'param_neuron_inhibitory']:
                    if neuron_type in section_data and variable in section_data[neuron_type]:
                        section_data[neuron_type][variable] = value
    
    # 수정된 dict로 새로운 Pydantic 모델 생성
    return SimulationParameters(**param_dict)
```

### 3. **create_linked_parameters() 독립 사용 지원**

#### 현재 Jupyter 사용 패턴:
```python
# 직접 호출 패턴
parameters = create_linked_parameters(folder_simulation, param)
```

#### Pydantic 통합 해결책:
```python
def create_linked_parameters_v2(results_path, parameters):
    \"\"\"하이브리드 지원: dict와 Pydantic 모델 모두 처리\"\"\"
    
    # 1. 입력 타입 확인 및 변환
    if hasattr(parameters, 'model_dump'):
        # Pydantic 모델
        param_dict = parameters.model_dump()
        is_pydantic = True
    else:
        # 기존 dict
        param_dict = parameters
        is_pydantic = False
    
    # 2. 기존 연결 로직 실행 (dict 기반)
    linked_dict = _create_linked_parameters_dict(results_path, param_dict)
    
    # 3. 출력 타입 결정
    if is_pydantic:
        # Pydantic 모델로 반환
        return SimulationParameters(**linked_dict)
    else:
        # dict로 반환 (하위 호환)
        return linked_dict
```

## 🎯 **업데이트된 통합 전략**

### Phase 1: 기본 통합 (완료) ✅
- run_exploration.py의 25줄 → 1줄 대체

### Phase 2: 파라미터 탐색 지원 (다음 우선순위) 🎯
1. **generate_parameter() Pydantic 지원**
2. **모듈 객체 → Pydantic 변환**
3. **파라미터 탐색 변수 적용 로직**

### Phase 3: 독립 함수 지원
1. **create_linked_parameters() 하이브리드 지원**
2. **Jupyter 노트북 호환성**

### Phase 4: 고급 기능
1. **복잡한 파라미터 섹션 스키마**
2. **성능 최적화**

## 🚨 **즉시 해결해야 할 이슈**

1. **모듈 객체 처리**: `example.parameter.test_nest` 모듈을 Pydantic으로 변환
2. **파라미터 탐색 로직**: `dict_variable` 적용 메커니즘
3. **중첩 구조 수정**: excitatory/inhibitory 뉴런 파라미터
4. **numpy 배열 지원**: `np.arange()` 등 탐색 범위

이 패턴들을 고려하지 않으면 **파라미터 탐색 워크플로우가 완전히 깨집니다**!"