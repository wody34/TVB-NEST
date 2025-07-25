"""
Pydantic을 사용한 현대적 Parameter Validation
- Type hints로 스키마 정의
- 자동 validation 및 conversion
- 훨씬 깔끔하고 유지보수 쉬움
"""

from pydantic import BaseModel, Field, validator, root_validator
from typing import List, Optional, Union
from pathlib import Path
import json

class CoSimulationParams(BaseModel):
    """Co-simulation parameters with automatic validation"""
    co_simulation: bool = Field(..., description="Enable co-simulation")
    nb_MPI_nest: int = Field(..., ge=1, le=1000, description="Number of MPI processes for NEST")
    level_log: int = Field(..., ge=0, le=4, description="Logging level (0-4)")
    cluster: bool = Field(default=False, description="Run on cluster")
    synchronization: Optional[float] = Field(None, gt=0.1, lt=1000.0)
    id_region_nest: Optional[List[int]] = Field(None, description="NEST region IDs")
    record_MPI: bool = Field(default=False)
    
    @validator('id_region_nest')
    def validate_region_ids(cls, v):
        if v is not None and len(v) == 0:
            raise ValueError("id_region_nest cannot be empty list")
        return v

class NestParams(BaseModel):
    """NEST simulation parameters"""
    sim_resolution: float = Field(..., gt=0.001, le=10.0, description="Simulation resolution")
    master_seed: int = Field(..., ge=1, le=2**31-1, description="Random seed")
    total_num_virtual_procs: int = Field(..., ge=1, le=1000)
    overwrite_files: bool = Field(default=True)
    print_time: bool = Field(default=True)
    verbosity: int = Field(default=20, ge=0, le=100)

class NestTopologyParams(BaseModel):
    """NEST topology parameters"""
    neuron_type: str = Field(..., description="Neuron model type")
    nb_region: int = Field(..., ge=1, le=10000, description="Number of regions")
    nb_neuron_by_region: int = Field(..., ge=1, le=100000, description="Neurons per region")
    percentage_inhibitory: float = Field(..., ge=0.0, le=1.0, description="Inhibitory neuron ratio")
    mean_I_ext: float = Field(default=0.0)
    sigma_I_ext: float = Field(default=0.0, ge=0.0)
    
    # Nested parameter objects
    param_neuron_excitatory: dict = Field(..., description="Excitatory neuron parameters")
    param_neuron_inhibitory: dict = Field(..., description="Inhibitory neuron parameters")

class SimulationParameters(BaseModel):
    """Complete simulation parameter set with cross-validation"""
    
    # Core parameters
    result_path: str = Field(..., description="Output directory path")
    begin: float = Field(..., ge=0.0, description="Simulation start time")
    end: float = Field(..., gt=0.0, description="Simulation end time")
    
    # Parameter sections
    param_co_simulation: CoSimulationParams
    param_nest: NestParams
    param_nest_topology: NestTopologyParams
    
    # Optional sections (validated only if co-simulation enabled)
    param_TR_nest_to_tvb: Optional[dict] = None
    param_TR_tvb_to_nest: Optional[dict] = None
    param_tvb_model: Optional[dict] = None
    param_tvb_connection: Optional[dict] = None
    
    @validator('end')
    def end_must_be_after_begin(cls, v, values):
        if 'begin' in values and v <= values['begin']:
            raise ValueError('end time must be greater than begin time')
        return v
    
    @root_validator
    def validate_co_simulation_requirements(cls, values):
        """Cross-validation: if co-simulation enabled, check required sections"""
        co_sim = values.get('param_co_simulation')
        if co_sim and co_sim.co_simulation:
            required_sections = ['param_TR_nest_to_tvb', 'param_TR_tvb_to_nest']
            for section in required_sections:
                if not values.get(section):
                    raise ValueError(f"Co-simulation requires {section} section")
        return values
    
    @validator('result_path')
    def validate_result_path(cls, v):
        """Ensure result path is valid and writable"""
        path = Path(v)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError) as e:
            raise ValueError(f"Cannot create result directory: {e}")
        return str(path.resolve())
    
    class Config:
        # Enable validation on assignment
        validate_assignment = True
        # Allow extra fields (for backward compatibility)
        extra = "allow"
        # Generate JSON schema
        schema_extra = {
            "example": {
                "result_path": "./simulation_results/",
                "begin": 0.0,
                "end": 200.0,
                "param_co_simulation": {
                    "co_simulation": True,
                    "nb_MPI_nest": 10,
                    "level_log": 1,
                    "cluster": False
                }
            }
        }

# 사용법: 기존 코드를 완전히 대체
def load_and_validate_parameters(parameters_file: str) -> SimulationParameters:
    """
    Pydantic을 사용한 안전한 파라미터 로딩
    - 자동 타입 변환
    - 자동 검증
    - 명확한 에러 메시지
    """
    param_file = Path(parameters_file)
    
    if not param_file.exists():
        raise FileNotFoundError(f"Parameter file not found: {param_file}")
    
    try:
        with param_file.open('r', encoding='utf-8') as f:
            raw_data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")
    
    # Pydantic이 모든 검증을 자동으로 수행
    try:
        return SimulationParameters(**raw_data)
    except Exception as e:
        raise ValueError(f"Parameter validation failed: {e}")

# 기존 run() 함수를 이렇게 간단하게 변경
def run_with_pydantic(parameters_file: str):
    """Pydantic 검증을 사용한 안전한 run 함수"""
    
    # 한 줄로 모든 검증 완료!
    params = load_and_validate_parameters(parameters_file)
    
    # 이제 params는 완전히 검증된 객체
    # IDE 자동완성도 완벽하게 작동
    print(f"Running simulation with {params.param_co_simulation.nb_MPI_nest} MPI processes")
    print(f"Logging level: {params.param_co_simulation.level_log}")
    print(f"Output directory: {params.result_path}")
    
    # Type-safe 접근
    if params.param_co_simulation.co_simulation:
        print("Co-simulation mode enabled")
        if params.param_co_simulation.id_region_nest:
            print(f"Target regions: {params.param_co_simulation.id_region_nest}")
    
    # 기존 로직 계속...

if __name__ == "__main__":
    # 테스트
    try:
        params = load_and_validate_parameters("example/short_simulation/parameter.json")
        print("✅ Validation successful!")
        print(f"Simulation time: {params.begin} -> {params.end}")
        
        # JSON Schema 생성 (문서화용)
        schema = SimulationParameters.schema()
        print("\n📋 Generated JSON Schema available for documentation")
        
    except Exception as e:
        print(f"❌ Validation failed: {e}")