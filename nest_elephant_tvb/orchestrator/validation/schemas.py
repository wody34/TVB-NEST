#  Copyright 2020 Forschungszentrum Jülich GmbH and Aix-Marseille Université
# "Licensed to the Apache Software Foundation (ASF) under one or more contributor license agreements; and to You under the Apache License, Version 2.0. "

"""
Pydantic schemas for TVB-NEST parameter validation.

This module defines the parameter validation schemas using Pydantic models,
providing type safety, validation, and backward compatibility for the
TVB-NEST co-simulation framework.
"""

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from typing import List, Optional, Dict, Any
from pathlib import Path


class CoSimulationParams(BaseModel):
    """Co-simulation configuration parameters with validation"""
    
    model_config = ConfigDict(
        populate_by_name=True,  # Allow both field names and aliases
        extra="allow"  # Allow extra fields for backward compatibility
    )
    
    co_simulation: bool = Field(..., alias="co-simulation", description="Enable co-simulation")
    nb_MPI_nest: int = Field(..., ge=1, le=1000, description="Number of MPI processes for NEST")
    level_log: int = Field(..., ge=0, le=4, description="Logging level (0-4)")
    cluster: bool = Field(default=False, description="Run on cluster")
    synchronization: Optional[float] = Field(None, gt=0.1, lt=1000.0, description="Synchronization time")
    id_region_nest: Optional[List[int]] = Field(None, description="NEST region IDs")
    record_MPI: bool = Field(default=False, description="Record MPI communications")
    
    @field_validator('id_region_nest')
    @classmethod
    def validate_region_ids(cls, v):
        """Validate that region IDs list is not empty if provided"""
        if v is not None and len(v) == 0:
            raise ValueError("id_region_nest cannot be empty list")
        return v


class NestParams(BaseModel):
    """NEST simulation parameters with validation"""
    
    model_config = ConfigDict(extra="allow")
    
    sim_resolution: float = Field(..., gt=0.001, le=10.0, description="Simulation resolution (ms)")
    master_seed: int = Field(..., ge=1, le=2**31-1, description="Random seed")
    total_num_virtual_procs: int = Field(..., ge=1, le=1000, description="Virtual processes")
    overwrite_files: bool = Field(default=True, description="Overwrite existing files")
    print_time: bool = Field(default=True, description="Print timing information")
    verbosity: int = Field(default=20, ge=0, le=100, description="NEST verbosity level")


class SimulationParameters(BaseModel):
    """Complete simulation parameter set with cross-validation"""
    
    model_config = ConfigDict(
        extra="allow",  # Backward compatibility - allow extra fields
        validate_assignment=True,  # Validate on assignment
        populate_by_name=True  # Allow field name and alias
    )
    
    result_path: str = Field(..., description="Output directory path")
    begin: float = Field(..., ge=0.0, description="Simulation start time")
    end: float = Field(..., gt=0.0, description="Simulation end time")
    
    # Core parameter sections
    param_co_simulation: CoSimulationParams
    param_nest: Optional[NestParams] = None
    
    # Optional parameter sections (as dicts for gradual migration)
    param_nest_topology: Optional[Dict[str, Any]] = None
    param_nest_connection: Optional[Dict[str, Any]] = None
    param_nest_background: Optional[Dict[str, Any]] = None
    param_tvb_model: Optional[Dict[str, Any]] = None
    param_tvb_connection: Optional[Dict[str, Any]] = None
    param_tvb_coupling: Optional[Dict[str, Any]] = None
    param_tvb_integrator: Optional[Dict[str, Any]] = None
    param_tvb_monitor: Optional[Dict[str, Any]] = None
    param_TR_nest_to_tvb: Optional[Dict[str, Any]] = None
    param_TR_tvb_to_nest: Optional[Dict[str, Any]] = None
    
    @field_validator('end')
    @classmethod
    def end_must_be_after_begin(cls, v, info):
        """Validate that end time is greater than begin time"""
        if info.data and 'begin' in info.data and v <= info.data['begin']:
            raise ValueError('end time must be greater than begin time')
        return v
    
    @model_validator(mode='after')
    def validate_co_simulation_requirements(self):
        """Validate cross-parameter dependencies for co-simulation"""
        if self.param_co_simulation and self.param_co_simulation.co_simulation:
            required_sections = ['param_TR_nest_to_tvb', 'param_TR_tvb_to_nest']
            for section in required_sections:
                if not getattr(self, section, None):
                    raise ValueError(f"Co-simulation requires {section} section")
        return self
    
    @field_validator('result_path')
    @classmethod
    def validate_result_path(cls, v):
        """Validate and resolve the result path to an absolute path."""
        # Directory creation as a side-effect of validation is best avoided.
        # The experiment runner is responsible for creating directories.
        return str(Path(v).resolve())