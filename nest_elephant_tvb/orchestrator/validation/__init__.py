#  Copyright 2020 Forschungszentrum Jülich GmbH and Aix-Marseille Université
# "Licensed to the Apache Software Foundation (ASF) under one or more contributor license agreements; and to You under the Apache License, Version 2.0. "

"""
Parameter validation module for TVB-NEST co-simulation framework.

This module provides Pydantic-based parameter validation with backward compatibility
and type safety for the orchestrator component.
"""

from .validators import ParameterValidator, ParameterValidationError
from .compatibility import BackwardCompatibilityManager

# Backward compatibility alias - ParameterIntegration now points to BackwardCompatibilityManager
# This maintains existing import paths while consolidating functionality
class ParameterIntegration:
    """Backward compatibility wrapper for ParameterIntegration -> BackwardCompatibilityManager migration"""
    
    @staticmethod
    def load_parameters_safe(parameters_file: str):
        """Legacy method name - redirects to BackwardCompatibilityManager"""
        return BackwardCompatibilityManager.load_parameters_safe_dict(parameters_file)
    
    @staticmethod  
    def get_typed_parameters(parameters_file: str):
        """Legacy method name - redirects to BackwardCompatibilityManager"""
        return BackwardCompatibilityManager.get_typed_parameters(parameters_file)

__all__ = [
    'ParameterValidator',
    'ParameterValidationError', 
    'ParameterIntegration',
    'BackwardCompatibilityManager'
]