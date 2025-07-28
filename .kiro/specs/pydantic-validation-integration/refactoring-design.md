# 기존 패턴 리팩토링 디자인

## 🔍 **현재 패턴의 문제점 분석**

### 1. **모듈 객체 기반 파라미터 관리의 문제**
```python
# 현재 문제적 패턴
from example.parameter import test_nest as parameter_test
parameter_test.param_co_simulation['co-simulation'] = True  # 모듈 수정
run_exploration_2D(path, parameter_test, {'g': [1.0]}, begin, end)
```

**문제점**:
- ❌ **전역 상태 변경**: 모듈 수정이 다른 코드에 영향
- ❌ **타입 안전성 없음**: IDE 자동완성 불가
- ❌ **테스트 어려움**: 모듈 상태 격리 불가
- ❌ **동시성 문제**: 멀티스레딩 환경에서 위험

### 2. **복잡한 introspection 로직의 문제**
```python
# 현재 복잡한 패턴
def generate_parameter(parameter_default, results_path, dict_variable=None):
    for parameters_name in dir(parameter_default):  # 런타임 속성 탐색
        if 'param' in parameters_name:
            parameters_values = getattr(parameter_default, parameters_name)  # 동적 접근
```

**문제점**:
- ❌ **런타임 에러 위험**: 속성 이름 오타 시 런타임에만 발견
- ❌ **성능 저하**: 매번 dir() + getattr() 호출
- ❌ **유지보수 어려움**: 로직이 복잡하고 이해하기 어려움

### 3. **파라미터 탐색 로직의 문제**
```python
# 현재 비효율적 패턴
for variable in dict_variable.keys():
    for parameters_name in dir(parameter_default):  # O(n²) 복잡도
        if 'param' in parameters_name:
            # 중첩 루프로 모든 섹션 탐색
```

**문제점**:
- ❌ **비효율적**: O(n²) 시간 복잡도
- ❌ **예측 불가능**: 어떤 파라미터가 수정될지 불명확
- ❌ **에러 처리 부족**: 존재하지 않는 파라미터 처리 없음

## 🎯 **개선된 디자인 제안**

### **핵심 원칙**
1. **불변성**: 파라미터 객체는 불변, 새로운 객체 생성
2. **타입 안전성**: Pydantic 모델로 컴파일 타임 검증
3. **명시적**: 파라미터 수정이 명확하고 예측 가능
4. **성능**: O(1) 파라미터 접근, 효율적인 탐색

### **Design 1: Parameter Builder 패턴** ⭐ **추천**

```python
class ParameterBuilder:
    \"\"\"불변 파라미터 빌더 - 함수형 스타일\"\"\"
    
    def __init__(self, base_params: SimulationParameters):
        self._params = base_params
    
    def with_co_simulation(self, **kwargs) -> 'ParameterBuilder':
        \"\"\"Co-simulation 파라미터 수정\"\"\"
        current = self._params.model_copy()
        for key, value in kwargs.items():
            setattr(current.param_co_simulation, key, value)
        return ParameterBuilder(current)
    
    def with_nest_params(self, **kwargs) -> 'ParameterBuilder':
        \"\"\"NEST 파라미터 수정\"\"\"
        current = self._params.model_copy()
        for key, value in kwargs.items():
            setattr(current.param_nest, key, value)
        return ParameterBuilder(current)
    
    def with_exploration_variable(self, variable: str, value: Any) -> 'ParameterBuilder':
        \"\"\"탐색 변수 적용 - 명시적이고 안전\"\"\"
        current = self._params.model_copy()
        
        # 명시적 매핑으로 어떤 파라미터가 수정되는지 명확
        variable_mapping = {
            'g': ['param_nest_connection.g', 'param_nest_topology.percentage_inhibitory'],
            'mean_I_ext': ['param_nest_topology.mean_I_ext'],
            'b': ['param_nest_topology.param_neuron_excitatory.b'],
            # 새로운 변수 추가 시 여기에 명시적으로 정의
        }
        
        if variable not in variable_mapping:
            raise ValueError(f\"Unknown exploration variable: {variable}\")
        
        # 타입 안전한 파라미터 수정
        for param_path in variable_mapping[variable]:
            self._set_nested_param(current, param_path, value)
        
        return ParameterBuilder(current)
    
    def build(self) -> SimulationParameters:
        \"\"\"최종 파라미터 객체 생성\"\"\"
        return self._params.model_copy()
    
    def _set_nested_param(self, params: SimulationParameters, path: str, value: Any):
        \"\"\"중첩 파라미터 안전하게 설정\"\"\"
        parts = path.split('.')
        obj = params
        for part in parts[:-1]:
            obj = getattr(obj, part)
        setattr(obj, parts[-1], value)

# 사용 예시
def create_exploration_parameters(base_config_file: str, exploration_vars: dict) -> SimulationParameters:
    \"\"\"새로운 파라미터 탐색 API\"\"\"
    # 1. 기본 파라미터 로드
    base_params = ParameterValidator.load_and_validate(base_config_file)
    
    # 2. 빌더 패턴으로 수정
    builder = ParameterBuilder(base_params)
    
    # 3. 탐색 변수 적용
    for variable, value in exploration_vars.items():
        builder = builder.with_exploration_variable(variable, value)
    
    # 4. 연결된 파라미터 생성
    return builder.build()
```

### **Design 2: Configuration Class 패턴**

```python
@dataclass
class ExplorationConfig:
    \"\"\"파라미터 탐색 설정\"\"\"
    base_config_file: str
    output_directory: str
    exploration_variables: Dict[str, List[Any]]
    simulation_time: Tuple[float, float]  # (begin, end)
    
    def generate_parameter_combinations(self) -> Iterator[Tuple[str, SimulationParameters]]:
        \"\"\"모든 파라미터 조합 생성\"\"\"
        variable_names = list(self.exploration_variables.keys())
        variable_values = list(self.exploration_variables.values())
        
        for combination in itertools.product(*variable_values):
            # 조합별 고유 이름 생성
            combo_name = '_'.join(f\"{name}_{value}\" for name, value in zip(variable_names, combination))
            
            # 파라미터 생성
            exploration_vars = dict(zip(variable_names, combination))
            params = create_exploration_parameters(self.base_config_file, exploration_vars)
            
            yield combo_name, params

class ParameterExplorer:
    \"\"\"파라미터 탐색 실행기\"\"\"
    
    def __init__(self, config: ExplorationConfig):
        self.config = config
    
    def run_exploration(self):
        \"\"\"전체 파라미터 탐색 실행\"\"\"
        for combo_name, params in self.config.generate_parameter_combinations():
            result_path = Path(self.config.output_directory) / combo_name
            
            # 파라미터 저장
            self.save_parameters(params, result_path)
            
            # 시뮬레이션 실행
            self.run_simulation(result_path / 'parameter.json')
    
    def save_parameters(self, params: SimulationParameters, result_path: Path):
        \"\"\"파라미터 저장 - Pydantic 네이티브\"\"\"
        result_path.mkdir(parents=True, exist_ok=True)
        
        # Pydantic 직렬화
        param_dict = params.model_dump(by_alias=True)
        param_dict.update({
            \"result_path\": str(result_path.resolve()) + \"/\",
            \"begin\": self.config.simulation_time[0],
            \"end\": self.config.simulation_time[1]
        })
        
        param_file = result_path / 'parameter.json'
        with param_file.open('w') as f:
            json.dump(param_dict, f, indent=2)
    
    def run_simulation(self, param_file: Path):
        \"\"\"시뮬레이션 실행\"\"\"
        from nest_elephant_tvb.orchestrator.run_exploration import run
        run(str(param_file))
```

### **Design 3: 새로운 사용 패턴**

```python
# 기존 복잡한 패턴 대체
# OLD:
# from example.parameter import test_nest as parameter_test
# parameter_test.param_co_simulation['co-simulation'] = True
# run_exploration_2D(path, parameter_test, {'g': [1.0]}, begin, end)

# NEW: 명확하고 타입 안전한 패턴
config = ExplorationConfig(
    base_config_file=\"example/short_simulation/parameter.json\",
    output_directory=\"./exploration_results\",
    exploration_variables={
        'g': [1.0, 1.5, 2.0],
        'mean_I_ext': [0.0, 50.0, 100.0]
    },
    simulation_time=(0.0, 200.0)
)

explorer = ParameterExplorer(config)
explorer.run_exploration()
```

### **Design 4: Jupyter 친화적 API**

```python
# Jupyter 노트북에서 간단한 사용
class SimpleParameterManager:
    \"\"\"Jupyter 환경을 위한 간단한 API\"\"\"
    
    @staticmethod
    def load_and_modify(config_file: str, **modifications) -> SimulationParameters:
        \"\"\"파라미터 로드 및 수정\"\"\"
        params = ParameterValidator.load_and_validate(config_file)
        
        # 간단한 수정 API
        for key, value in modifications.items():
            if '.' in key:  # 중첩 접근: 'param_nest.sim_resolution'
                parts = key.split('.')
                obj = params
                for part in parts[:-1]:
                    obj = getattr(obj, part)
                setattr(obj, parts[-1], value)
            else:  # 탑레벨 접근
                setattr(params, key, value)
        
        return params
    
    @staticmethod
    def save_and_run(params: SimulationParameters, output_dir: str, begin: float = 0.0, end: float = 100.0):
        \"\"\"파라미터 저장 및 시뮬레이션 실행\"\"\"
        # 파라미터 저장
        result_path = Path(output_dir)
        result_path.mkdir(parents=True, exist_ok=True)
        
        param_dict = params.model_dump(by_alias=True)
        param_dict.update({
            \"result_path\": str(result_path.resolve()) + \"/\",
            \"begin\": begin,
            \"end\": end
        })
        
        param_file = result_path / 'parameter.json'
        with param_file.open('w') as f:
            json.dump(param_dict, f, indent=2)
        
        # 시뮬레이션 실행
        from nest_elephant_tvb.orchestrator.run_exploration import run
        run(str(param_file))

# Jupyter 사용 예시
params = SimpleParameterManager.load_and_modify(
    \"example/short_simulation/parameter.json\",
    **{
        'param_co_simulation.co_simulation': True,
        'param_nest.sim_resolution': 0.05
    }
)

SimpleParameterManager.save_and_run(params, \"./my_simulation\", 0.0, 100.0)
```

## 🎯 **마이그레이션 전략**

### **Phase 1: 새로운 API 도입** (하위 호환 유지)
```python
# 기존 함수들을 새로운 API로 래핑
def run_exploration_2D_v2(base_config: str, output_dir: str, exploration_vars: dict, begin: float, end: float):
    \"\"\"기존 API 호환성 유지\"\"\"
    config = ExplorationConfig(
        base_config_file=base_config,
        output_directory=output_dir,
        exploration_variables=exploration_vars,
        simulation_time=(begin, end)
    )
    
    explorer = ParameterExplorer(config)
    explorer.run_exploration()

# 기존 코드 최소 변경으로 마이그레이션
# OLD: run_exploration_2D(path, parameter_test, {'g': [1.0]}, begin, end)
# NEW: run_exploration_2D_v2(\"config.json\", path, {'g': [1.0]}, begin, end)
```

### **Phase 2: 점진적 마이그레이션**
- 새로운 테스트 스크립트부터 새 API 사용
- 기존 스크립트는 호환성 레이어로 유지
- Jupyter 노트북은 SimpleParameterManager 사용

### **Phase 3: 레거시 제거**
- 기존 복잡한 함수들 deprecated
- 새로운 API로 완전 전환

## 🚀 **장점**

1. **타입 안전성**: 컴파일 타임 에러 검출
2. **명시적**: 파라미터 수정이 예측 가능
3. **성능**: O(1) 파라미터 접근
4. **테스트 용이**: 불변 객체로 격리된 테스트
5. **확장성**: 새로운 탐색 변수 쉽게 추가
6. **IDE 지원**: 자동완성 및 타입 힌트

이 디자인으로 가면 어떨까요? 기존 복잡한 패턴을 깔끔하게 정리하면서 Pydantic의 장점을 최대한 활용할 수 있습니다."