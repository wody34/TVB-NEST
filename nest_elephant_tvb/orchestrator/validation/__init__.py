#  Copyright 2020 Forschungszentrum Jülich GmbH and Aix-Marseille Université
# "Licensed to the Apache Software Foundation (ASF) under one or more contributor license agreements; and to You under the Apache License, Version 2.0. "

"""
Parameter validation module for TVB-NEST co-simulation framework.

This module provides Pydantic-based parameter validation with backward compatibility
and type safety for the orchestrator component.
"""

from .validators import ParameterValidator, ParameterValidationError
from .integration import ParameterIntegration

__all__ = [
    'ParameterValidator',
    'ParameterValidationError', 
    'ParameterIntegration'
]