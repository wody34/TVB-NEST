#  Copyright 2020 Forschungszentrum Jülich GmbH and Aix-Marseille Université
# "Licensed to the Apache Software Foundation (ASF) under one or more contributor license agreements; and to You under the Apache License, Version 2.0. "

"""
Integration layer between Pydantic validation and existing code.

This module provides backward compatibility and gradual migration support
for integrating Pydantic validation with the existing parameter system.
"""

from typing import Dict, Any
from .validators import ParameterValidator, ParameterValidationError
from .schemas import SimulationParameters


class ParameterIntegration:
    """Integration layer between Pydantic validation and existing code"""
    
    @staticmethod
    def load_parameters_safe(parameters_file: str) -> Dict[str, Any]:
        """
        Load parameters with Pydantic validation, fallback to original method
        This allows gradual migration and testing
        """
        try:
            validated_params = ParameterValidator.load_and_validate(parameters_file)
            return validated_params.model_dump(by_alias=True)
        except ParameterValidationError as e:
            # Log validation error but don't break existing functionality
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Pydantic validation failed, using original method: {e}")
            
            # Fallback to original parameter loading
            return _load_parameters_original(parameters_file)
    
    @staticmethod
    def get_typed_parameters(parameters_file: str) -> SimulationParameters:
        """Get fully typed parameter object for new code"""
        return ParameterValidator.load_and_validate(parameters_file)


def _load_parameters_original(parameters_file: str) -> Dict[str, Any]:
    """Original parameter loading method for fallback"""
    # Placeholder for original parameter loading logic
    # This would be implemented with the current parameter loading code
    import json
    from pathlib import Path
    
    param_file = Path(parameters_file)
    with param_file.open('r', encoding='utf-8') as f:
        return json.load(f)