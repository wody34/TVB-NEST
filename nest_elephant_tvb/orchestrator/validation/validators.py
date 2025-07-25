#  Copyright 2020 Forschungszentrum Jülich GmbH and Aix-Marseille Université
# "Licensed to the Apache Software Foundation (ASF) under one or more contributor license agreements; and to You under the Apache License, Version 2.0. "

"""
Parameter validation service classes.

This module provides the service layer for parameter validation,
including error handling and integration with the existing codebase.
"""

from pathlib import Path
import json
from typing import Dict, Any, Union
from .schemas import SimulationParameters


class ParameterValidationError(Exception):
    """Custom exception for parameter validation failures"""
    pass


class ParameterValidator:
    """Service for parameter validation and loading"""
    
    @staticmethod
    def load_and_validate(parameters_file: Union[str, Path]) -> SimulationParameters:
        """Load and validate parameters from JSON file"""
        param_file = Path(parameters_file)
        
        if not param_file.exists():
            raise ParameterValidationError(f"Parameter file not found: {param_file}")
        
        try:
            with param_file.open('r', encoding='utf-8') as f:
                raw_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ParameterValidationError(f"Invalid JSON: {e}")
        
        try:
            return SimulationParameters(**raw_data)
        except Exception as e:
            raise ParameterValidationError(f"Parameter validation failed: {e}")
    
    @staticmethod
    def validate_dict(raw_data: Dict[str, Any]) -> SimulationParameters:
        """Validate parameters from dictionary"""
        try:
            return SimulationParameters(**raw_data)
        except Exception as e:
            raise ParameterValidationError(f"Parameter validation failed: {e}")