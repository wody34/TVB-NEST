# 실제 사용 패턴 심층 분석

## 🔍 **실제 사용 패턴 완전 분석**

### **Pattern 1: 실험별 설정 변경** ⭐ **핵심 패턴**

#### 각 실험 스크립트의 특화 설정:

```python
# tests/run_co-sim.py - Co-simulation 실험
def run_exploration(path, begin, end):
    parameter_test.param_co_simulation['co-simulation'] = True
    parameter_test.param_co_simulation['nb_MPI_nest'] = 4
    parameter_test.param_nest['total_num_virtual_procs'] = parameter_test.param_co_simulation['nb_MPI_nest']
    parameter_test.param_co_simulation['id_region_nest'] = [1,2]
    parameter_test.param_co_simulation['synchronization'] = 3.5
    run_exploration_2D(path, parameter_test, {'g':np.arange(1.0, 1.2, 0.5), 'mean_I_ext': [0.0]}, begin, end)

# tests/run_tvb_one.py - TVB 단일 영역 실험  
def run_exploration(path, begin, end):
    parameter_test.param_co_simulation['nb_MPI_nest'] = 0  # TVB만 사용
    parameter_test.param_nest_topology['nb_region'] = 1    # 단일 영역
    parameter_test.param_tvb_monitor['Raw'] = True         # Raw 모니터링
    run_exploration_2D(path, parameter_test, {'b':[10.0,7.0,1.0], 'mean_I_ext': [0.0]}, begin, end)

# tests/run_nest_saving.py - NEST 저장 실험
def run_exploration(path, begin, end):
    parameter_test.param_co_simulation['co-simulation'] = False
    parameter_test.param_co_simulation['nb_MPI_nest'] = 1
    parameter_test.param_nest['total_num_virtual_procs'] = 10
    parameter_test.param_co_simulation['record_MPI'] = True  # MPI 기록 활성화
    parameter_test.param_record_MPI['save_step'] = 10        # 저장 주기
    run_exploration_2D(path, parameter_test, {'g':np.arange(0.0, 1.0, 0.5), 'mean_I_ext': np.arange(0.0, 100.0, 50.0)}, begin, end)
```

### **Pattern 2: 파라미터 탐색 변수** ⭐ **핵심 패턴**

#### 실제 탐색되는 과학적 파라미터들:

```python
# 1. 신경망 연결성 파라미터
{'g': np.arange(1.0, 1.2, 0.5), 'mean_I_ext': [0.0]}           # 흥분성/억제성 비율
{'g': np.arange(0.0, 1.0, 0.5), 'mean_I_ext': np.arange(0.0, 100.0, 50.0)}  # 2D 그리드 탐색

# 2. 뉴런 모델 파라미터  
{'b': [10.0, 7.0, 1.0], 'mean_I_ext': [0.0]}                   # 적응 파라미터

# 3. 단일 값 테스트
{'g': [1.0], 'mean_I_ext': [0.0]}                              # 단일 조건 테스트
```

### **Pattern 3: Jupyter 노트북 사용** ⭐ **중요 패턴**

#### 점진적 파라미터 구성:

```python
# example/demonstration_mouse_brain.ipynb
param = {}

# 섹션별로 점진적 구성
param['param_nest'] = {
    \"sim_resolution\": 0.1,
    \"master_seed\": 46,
    # ...
}

param['param_nest_topology'] = {
    \"neuron_type\": \"aeif_cond_exp\",
    # ...
}

# 나중에 업데이트
param['param_nest_topology'].update({
    \"mean_I_ext\": 0.0,
    \"sigma_I_ext\": 0.0,
    # ...
})

# 최종 사용
parameters = create_linked_parameters(folder_simulation, param)
save_parameter(parameters, folder_simulation, begin, end)
```

## 🎯 **사용 패턴 기반 최적 디자인 결정**

### **핵심 요구사항 분석**

1. **실험별 설정 변경**: 각 실험마다 다른 시뮬레이션 모드 (co-sim, TVB-only, NEST-only)
2. **파라미터 탐색**: 과학적 파라미터의 체계적 탐색 (1D, 2D 그리드)
3. **점진적 구성**: Jupyter에서 섹션별로 파라미터 구성
4. **타입 안전성**: 현재 런타임 에러가 많음
5. **재사용성**: 기본 설정을 베이스로 실험별 변형

### **최적 디자인: Hybrid Builder + Configuration** ⭐ **추천**

#### **Design A: Experiment Configuration 패턴**

```python
@dataclass
class ExperimentConfig:
    \"\"\"실험별 설정을 명시적으로 정의\"\"\"
    name: str
    base_config: str = \"example/short_simulation/parameter.json\"
    
    # 실험별 고정 설정
    simulation_mode: Literal['co-simulation', 'nest-only', 'tvb-only'] = 'co-simulation'
    nb_regions: int = 104
    mpi_processes: int = 4
    
    # 탐색할 파라미터
    exploration_params: Dict[str, List[float]] = field(default_factory=dict)
    
    # 실험별 특수 설정
    custom_overrides: Dict[str, Any] = field(default_factory=dict)

# 실험 정의
CO_SIM_EXPERIMENT = ExperimentConfig(
    name=\"co-simulation\",
    simulation_mode=\"co-simulation\",
    mpi_processes=4,
    exploration_params={
        'g': [1.0, 1.1, 1.2],
        'mean_I_ext': [0.0]
    },
    custom_overrides={
        'param_co_simulation.id_region_nest': [1, 2],
        'param_co_simulation.synchronization': 3.5
    }
)

TVB_ONE_EXPERIMENT = ExperimentConfig(
    name=\"tvb-single-region\",
    simulation_mode=\"tvb-only\",
    nb_regions=1,
    mpi_processes=0,
    exploration_params={
        'b': [10.0, 7.0, 1.0],
        'mean_I_ext': [0.0]
    },
    custom_overrides={
        'param_tvb_monitor.Raw': True
    }
)
```

#### **Design B: Fluent Parameter Builder**

```python
class ParameterBuilder:
    \"\"\"유창한 API로 파라미터 구성\"\"\"
    
    def __init__(self, base_config: str):
        self.params = ParameterValidator.load_and_validate(base_config)
    
    # 실험 모드 설정
    def for_co_simulation(self, mpi_processes: int = 4, regions: List[int] = [1, 2]) -> 'ParameterBuilder':
        self.params.param_co_simulation.co_simulation = True
        self.params.param_co_simulation.nb_MPI_nest = mpi_processes
        self.params.param_nest.total_num_virtual_procs = mpi_processes
        self.params.param_co_simulation.id_region_nest = regions
        return self
    
    def for_tvb_only(self, nb_regions: int = 1) -> 'ParameterBuilder':
        self.params.param_co_simulation.nb_MPI_nest = 0
        self.params.param_nest_topology.nb_region = nb_regions
        return self
    
    def for_nest_saving(self, save_step: int = 10) -> 'ParameterBuilder':
        self.params.param_co_simulation.co_simulation = False
        self.params.param_co_simulation.record_MPI = True
        self.params.param_record_MPI.save_step = save_step
        return self
    
    # 파라미터 탐색
    def explore(self, **params) -> Iterator[Tuple[str, SimulationParameters]]:
        \"\"\"파라미터 조합 생성\"\"\"
        param_names = list(params.keys())
        param_values = list(params.values())
        
        for combination in itertools.product(*param_values):
            # 조합별 파라미터 적용
            modified_params = self.params.model_copy()
            combo_name = \"_\".join(f\"{name}_{value}\" for name, value in zip(param_names, combination))
            
            for param_name, value in zip(param_names, combination):
                self._apply_exploration_param(modified_params, param_name, value)
            
            yield combo_name, modified_params
    
    def _apply_exploration_param(self, params: SimulationParameters, param_name: str, value: float):
        \"\"\"탐색 파라미터 적용 - 명시적 매핑\"\"\"
        param_mapping = {
            'g': lambda p, v: setattr(p.param_nest_connection, 'g', v),
            'mean_I_ext': lambda p, v: setattr(p.param_nest_topology, 'mean_I_ext', v),
            'b': lambda p, v: setattr(p.param_nest_topology.param_neuron_excitatory, 'b', v),
        }
        
        if param_name not in param_mapping:
            raise ValueError(f\"Unknown exploration parameter: {param_name}\")
        
        param_mapping[param_name](params, value)

# 사용 예시
def run_co_simulation_experiment(output_dir: str, begin: float, end: float):
    \"\"\"Co-simulation 실험 실행\"\"\"
    builder = ParameterBuilder(\"example/short_simulation/parameter.json\")
    
    # 실험 설정
    builder.for_co_simulation(mpi_processes=4, regions=[1, 2])
    
    # 파라미터 탐색 실행
    for combo_name, params in builder.explore(g=[1.0, 1.1, 1.2], mean_I_ext=[0.0]):
        result_path = Path(output_dir) / combo_name
        
        # 시뮬레이션 실행
        run_single_simulation(params, result_path, begin, end)

def run_tvb_single_region_experiment(output_dir: str, begin: float, end: float):
    \"\"\"TVB 단일 영역 실험 실행\"\"\"
    builder = ParameterBuilder(\"example/short_simulation/parameter.json\")
    
    # 실험 설정
    builder.for_tvb_only(nb_regions=1)
    
    # 파라미터 탐색 실행
    for combo_name, params in builder.explore(b=[10.0, 7.0, 1.0], mean_I_ext=[0.0]):
        result_path = Path(output_dir) / combo_name
        run_single_simulation(params, result_path, begin, end)
```

#### **Design C: Jupyter 친화적 Simple API**

```python
class SimpleExperiment:
    \"\"\"Jupyter 노트북을 위한 간단한 API\"\"\"
    
    @staticmethod
    def co_simulation(output_dir: str, exploration_params: dict, begin: float = 0.0, end: float = 100.0):
        \"\"\"Co-simulation 실험 원라이너\"\"\"
        builder = ParameterBuilder(\"example/short_simulation/parameter.json\")
        builder.for_co_simulation()
        
        for combo_name, params in builder.explore(**exploration_params):
            result_path = Path(output_dir) / combo_name
            run_single_simulation(params, result_path, begin, end)
    
    @staticmethod
    def tvb_only(output_dir: str, exploration_params: dict, nb_regions: int = 1, begin: float = 0.0, end: float = 100.0):
        \"\"\"TVB 전용 실험 원라이너\"\"\"
        builder = ParameterBuilder(\"example/short_simulation/parameter.json\")
        builder.for_tvb_only(nb_regions=nb_regions)
        
        for combo_name, params in builder.explore(**exploration_params):
            result_path = Path(output_dir) / combo_name
            run_single_simulation(params, result_path, begin, end)

# Jupyter 사용 예시
# 기존: 복잡한 모듈 수정 + run_exploration_2D 호출
# 새로운: 간단한 원라이너
SimpleExperiment.co_simulation(
    \"./co_sim_results\",
    {'g': [1.0, 1.1, 1.2], 'mean_I_ext': [0.0]},
    begin=0.0, end=200.0
)

SimpleExperiment.tvb_only(
    \"./tvb_results\", 
    {'b': [10.0, 7.0, 1.0], 'mean_I_ext': [0.0]},
    nb_regions=1,
    begin=0.0, end=1000.0
)
```

## 🎯 **최종 추천: Hybrid Builder 패턴**

### **이유**:

1. **실험별 설정**: `for_co_simulation()`, `for_tvb_only()` 등 명시적 실험 모드
2. **파라미터 탐색**: `explore()` 메서드로 타입 안전한 탐색
3. **Jupyter 친화적**: `SimpleExperiment` 클래스로 원라이너 지원
4. **점진적 마이그레이션**: 기존 함수들을 래핑하여 하위 호환성 유지
5. **타입 안전성**: Pydantic 모델 기반으로 컴파일 타임 검증

### **vs Hydra 비교**:

| 측면 | Builder 패턴 | Hydra |
|------|-------------|-------|
| **실험별 설정** | ✅ 메서드 체이닝으로 명시적 | 🟡 YAML 설정 파일 |
| **파라미터 탐색** | ✅ 프로그래밍 방식 제어 | ✅ 내장 sweep 기능 |
| **Jupyter 지원** | ✅ 완벽 지원 | ❌ CLI 중심 |
| **기존 코드 호환** | ✅ 점진적 마이그레이션 | ❌ 전면 리팩토링 |
| **타입 안전성** | ✅ Pydantic 기반 | 🟡 기본적 |

**결론**: 현재 사용 패턴에는 **Builder 패턴이 Hydra보다 적합**합니다!

Builder 패턴으로 진행할까요?"