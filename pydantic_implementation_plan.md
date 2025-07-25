# Pydantic 즉시 적용 계획

## 🎯 목표
현재 25줄의 수동 검증 코드를 Pydantic 1줄로 대체하여 안정성과 생산성 극대화

## ⏱️ 예상 소요시간: 2시간

### 1단계: 기본 스키마 정의 (30분)
```python
# nest_elephant_tvb/orchestrator/validation.py (새 파일)
from pydantic import BaseModel, Field
from typing import List, Optional

class CoSimulationParams(BaseModel):
    co_simulation: bool = Field(..., alias="co-simulation")
    nb_MPI_nest: int = Field(..., ge=1, le=1000)
    level_log: int = Field(..., ge=0, le=4)
    cluster: bool = Field(default=False)
    id_region_nest: Optional[List[int]] = None

class SimulationParameters(BaseModel):
    result_path: str
    begin: float = Field(..., ge=0.0)
    end: float = Field(..., gt=0.0)
    param_co_simulation: CoSimulationParams
    
    class Config:
        extra = "allow"  # 기존 파라미터 호환성
```

### 2단계: 기존 코드 교체 (30분)
```python
# nest_elephant_tvb/orchestrator/run_exploration.py 수정
from .validation import SimulationParameters

def run(parameters_file):
    param_file = Path(parameters_file)
    if not param_file.exists():
        raise FileNotFoundError(f"Parameter file not found: {param_file}")
    
    with param_file.open('r', encoding='utf-8') as f:
        raw_data = json.load(f)
    
    # 25줄 검증 코드를 1줄로 대체!
    params = SimulationParameters(**raw_data)
    
    # 이제 타입 안전하게 사용
    if params.param_co_simulation.co_simulation:
        print(f"MPI processes: {params.param_co_simulation.nb_MPI_nest}")
```

### 3단계: 테스트 및 검증 (30분)
```bash
# Docker 컨테이너에서 테스트
docker exec -it tvb-nest-dev bash
cd /home
python3 nest_elephant_tvb/orchestrator/run_exploration.py example/short_simulation/parameter.json
```

### 4단계: 추가 파라미터 섹션 확장 (30분)
```python
class NestParams(BaseModel):
    sim_resolution: float = Field(..., gt=0.001, le=10.0)
    master_seed: int = Field(..., ge=1, le=2**31-1)
    # ... 추가 필드들

class SimulationParameters(BaseModel):
    # ... 기존 필드들
    param_nest: Optional[NestParams] = None
    param_nest_topology: Optional[dict] = None  # 점진적 확장
```

## 🎉 즉시 얻는 이익

### ✅ 안정성
- KeyError 완전 제거
- 타입 오류 사전 방지
- 범위 검증 자동화

### ✅ 생산성
- IDE 자동완성 완벽 지원
- 25줄 → 1줄로 코드 간소화
- 새 파라미터 추가 시 자동 검증

### ✅ 유지보수성
- 스키마 중앙 관리
- 자동 문서화 (JSON Schema)
- 명확한 에러 메시지

### ✅ 과학적 재현성
- 파라미터 검증으로 실험 오류 방지
- 일관된 데이터 구조 보장
- 버전 관리 용이

## 🚀 다음 단계 (선택사항)

### Phase 2: CLI 개선 (Typer + Rich)
- 아름다운 진행 표시
- 파라미터 override 기능
- 대화형 설정

### Phase 3: 실험 관리 (Hydra)
- 자동 parameter sweeps
- 결과 체계적 관리
- 멀티런 실험 지원

## 💡 핵심 메시지
**Pydantic 먼저 적용하면 나머지 기술들의 효과가 배가됩니다!**
- 안정적인 파라미터 → 신뢰할 수 있는 CLI
- 검증된 설정 → 효과적인 실험 관리
- 타입 안전성 → 버그 없는 확장