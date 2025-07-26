#  Copyright 2020 Forschungszentrum Jülich GmbH and Aix-Marseille Université
# "Licensed to the Apache Software Foundation (ASF) under one or more contributor license agreements; and to You under the Apache License, Version 2.0. "

"""
Backward compatibility layer for gradual migration to Pydantic validation.
Provides safe parameter loading with fallback to legacy validation.
"""

import json
import logging
from pathlib import Path
from typing import Union, Dict, Any, Optional
import types

from .validators import ParameterValidator
from .schemas import SimulationParameters

logger = logging.getLogger(__name__)


class BackwardCompatibilityManager:
    """
    Manages backward compatibility during migration to Pydantic validation.
    Provides safe parameter loading with fallback mechanisms.
    """
    
    @staticmethod
    def convert_module_to_pydantic(parameter_module) -> SimulationParameters:
        """
        Convert Python module object (like example.parameter.test_nest) to Pydantic model.
        
        This handles the critical pattern where parameter_default is a module object
        with attributes like param_co_simulation, param_nest, etc.
        
        Args:
            parameter_module: Python module object with parameter attributes
            
        Returns:
            SimulationParameters: Validated Pydantic model
            
        Raises:
            ValueError: If module structure is invalid or conversion fails
        """
        if not isinstance(parameter_module, types.ModuleType):
            raise ValueError(f"Expected module object, got {type(parameter_module)}")
        
        logger.info(f"Converting module {parameter_module.__name__} to Pydantic model")
        
        # Extract all parameter attributes from module
        param_dict = {}
        param_attributes = []
        
        for attr_name in dir(parameter_module):
            # Look for attributes that start with 'param' and are not private
            if 'param' in attr_name and not attr_name.startswith('_'):
                try:
                    attr_value = getattr(parameter_module, attr_name)
                    # Only include dict-like attributes (actual parameters)
                    if isinstance(attr_value, dict):
                        param_dict[attr_name] = attr_value
                        param_attributes.append(attr_name)
                except AttributeError:
                    continue
        
        if not param_dict:
            raise ValueError(f"No parameter attributes found in module {parameter_module.__name__}")
        
        logger.debug(f"Found parameter attributes: {param_attributes}")
        
        # Add required fields that might not be in module
        if 'result_path' not in param_dict:
            param_dict['result_path'] = './default_results/'
        if 'begin' not in param_dict:
            param_dict['begin'] = 0.0
        if 'end' not in param_dict:
            param_dict['end'] = 100.0
        
        try:
            # Create Pydantic model
            pydantic_model = SimulationParameters(**param_dict)
            logger.info("✅ Successfully converted module to Pydantic model")
            return pydantic_model
            
        except Exception as e:
            logger.error(f"Failed to convert module to Pydantic: {e}")
            raise ValueError(f"Module conversion failed: {e}")
    
    @staticmethod
    def apply_exploration_variables(params: SimulationParameters, 
                                  dict_variable: Dict[str, Any]) -> SimulationParameters:
        """
        Apply parameter exploration variables to Pydantic model.
        
        This replicates the complex logic from generate_parameter() where
        exploration variables are applied to multiple parameter sections.
        
        Args:
            params: Pydantic model with base parameters
            dict_variable: Dictionary of variables to explore (e.g., {'g': 1.5, 'mean_I_ext': 0.0})
            
        Returns:
            SimulationParameters: New model with exploration variables applied
        """
        if not dict_variable:
            return params
            
        logger.info(f"Applying exploration variables: {dict_variable}")
        
        # Convert to dict for modification
        param_dict = params.model_dump()
        
        for variable_name, variable_value in dict_variable.items():
            logger.debug(f"Applying {variable_name} = {variable_value}")
            
            # Use recursive search to find and apply the variable
            applied = BackwardCompatibilityManager._apply_variable_recursive(
                param_dict, variable_name, variable_value
            )
            
            if applied:
                logger.debug(f"Successfully applied {variable_name} = {variable_value}")
            else:
                logger.warning(f"Variable {variable_name} not found in parameter structure")
        
        # Create new Pydantic model with modified parameters
        try:
            modified_params = SimulationParameters(**param_dict)
            logger.info("✅ Successfully applied exploration variables")
            return modified_params
        except Exception as e:
            logger.error(f"Failed to apply exploration variables: {e}")
            raise ValueError(f"Exploration variable application failed: {e}")
    
    @staticmethod
    def _apply_variable_recursive(data: Dict[str, Any], variable_name: str, 
                                variable_value: Any, path: str = "") -> bool:
        """
        Recursively search and apply variable in nested dictionary structure.
        
        Args:
            data: Dictionary to search in
            variable_name: Name of variable to find
            variable_value: Value to set
            path: Current path for logging (used internally)
            
        Returns:
            True if variable was found and applied, False otherwise
        """
        applied = False
        
        # Check direct keys in current level
        if variable_name in data:
            data[variable_name] = variable_value
            logger.debug(f"Applied {variable_name} = {variable_value} at {path or 'root'}")
            applied = True
        
        # Recursively search in nested dictionaries
        for key, value in data.items():
            if isinstance(value, dict):
                current_path = f"{path}.{key}" if path else key
                if BackwardCompatibilityManager._apply_variable_recursive(
                    value, variable_name, variable_value, current_path
                ):
                    applied = True
        
        return applied
    
    @staticmethod
    def safe_load_parameters(parameters_file: Union[str, Path]) -> Union[SimulationParameters, Dict[str, Any]]:
        """
        Safely load parameters with Pydantic validation and fallback to legacy.
        
        Args:
            parameters_file: Path to parameter file
            
        Returns:
            Either validated Pydantic model or legacy dict
            
        Raises:
            FileNotFoundError: If parameter file doesn't exist
            ValueError: If JSON is invalid and fallback also fails
        """
        try:
            # Try new Pydantic validation first
            logger.info("Attempting Pydantic parameter validation")
            params = ParameterValidator.load_and_validate(parameters_file)
            logger.info("✅ Pydantic validation successful")
            return params
            
        except Exception as pydantic_error:
            # Log the Pydantic error for debugging
            logger.warning(f"Pydantic validation failed: {pydantic_error}")
            logger.info("Falling back to legacy parameter validation")
            
            try:
                # Fallback to legacy validation
                params_dict = BackwardCompatibilityManager._load_legacy_parameters(parameters_file)
                logger.info("✅ Legacy validation successful")
                return params_dict
                
            except Exception as legacy_error:
                # Both methods failed
                logger.error(f"Both Pydantic and legacy validation failed")
                logger.error(f"Pydantic error: {pydantic_error}")
                logger.error(f"Legacy error: {legacy_error}")
                raise ValueError(
                    f"Parameter validation failed with both methods. "
                    f"Pydantic: {pydantic_error}. Legacy: {legacy_error}"
                )
    
    @staticmethod
    def _load_legacy_parameters(parameters_file: Union[str, Path]) -> Dict[str, Any]:
        """
        Legacy parameter loading and validation (original 25-line validation).
        
        Args:
            parameters_file: Path to parameter file
            
        Returns:
            Dictionary with validated parameters
            
        Raises:
            FileNotFoundError: If parameter file doesn't exist
            ValueError: If validation fails
        """
        # Load parameters using pathlib and context manager
        param_file = Path(parameters_file)
        if not param_file.exists():
            raise FileNotFoundError(f"Parameter file not found: {param_file}")
        
        try:
            with param_file.open('r', encoding='utf-8') as f:
                parameters = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in parameter file: {e}")
        
        # Basic parameter validation
        required_keys = ['param_co_simulation', 'result_path', 'begin', 'end']
        for key in required_keys:
            if key not in parameters:
                raise KeyError(f"Missing required parameter: {key}")
        
        # Validate critical co-simulation parameters
        co_sim = parameters['param_co_simulation']
        required_co_sim_keys = ['co-simulation', 'level_log']
        for key in required_co_sim_keys:
            if key not in co_sim:
                raise KeyError(f"Missing required co-simulation parameter: {key}")
        
        # Validate level_log range
        level_log = co_sim['level_log']
        if not isinstance(level_log, int) or not (0 <= level_log <= 4):
            raise ValueError(f"level_log must be integer 0-4, got: {level_log}")
        
        # Validate MPI process count if co-simulation enabled
        if co_sim.get('co-simulation', False):
            if 'nb_MPI_nest' not in co_sim:
                raise KeyError("Missing nb_MPI_nest for co-simulation")
            nb_mpi = co_sim['nb_MPI_nest']
            if not isinstance(nb_mpi, int) or nb_mpi < 1:
                raise ValueError(f"nb_MPI_nest must be positive integer, got: {nb_mpi}")
        
        return parameters
    
    @staticmethod
    def get_parameter_value(params: Union[SimulationParameters, Dict[str, Any]], 
                          key_path: str) -> Any:
        """
        Get parameter value from either Pydantic model or dict.
        
        Args:
            params: Either Pydantic model or dict
            key_path: Dot-separated path like 'param_co_simulation.level_log'
            
        Returns:
            Parameter value
        """
        if hasattr(params, 'model_dump'):
            # Pydantic model - use attribute access
            obj = params
            for key in key_path.split('.'):
                obj = getattr(obj, key)
            return obj
        else:
            # Dictionary - use key access
            obj = params
            for key in key_path.split('.'):
                obj = obj[key]
            return obj
    
    @staticmethod
    def is_pydantic_model(params: Union[SimulationParameters, Dict[str, Any]]) -> bool:
        """
        Check if parameters are Pydantic model or legacy dict.
        
        Args:
            params: Parameters to check
            
        Returns:
            True if Pydantic model, False if dict
        """
        return hasattr(params, 'model_dump')
    
    @staticmethod
    def load_parameters_safe_dict(parameters_file: str) -> Dict[str, Any]:
        """
        Load parameters with Pydantic validation, fallback to original method.
        Always returns dictionary format for backward compatibility.
        
        This method allows gradual migration and testing by providing
        the same interface as the legacy ParameterIntegration class.
        
        Args:
            parameters_file: Path to parameter file
            
        Returns:
            Dictionary with validated parameters
        """
        try:
            from .validators import ParameterValidator, ParameterValidationError
            validated_params = ParameterValidator.load_and_validate(parameters_file)
            return validated_params.model_dump(by_alias=True)
        except Exception as e:
            # Log validation error but don't break existing functionality
            logger.warning(f"Pydantic validation failed, using legacy method: {e}")
            
            # Fallback to comprehensive legacy parameter loading
            return BackwardCompatibilityManager._load_legacy_parameters(parameters_file)
    
    @staticmethod
    def get_typed_parameters(parameters_file: str) -> SimulationParameters:
        """
        Get fully typed parameter object for new code.
        
        Args:
            parameters_file: Path to parameter file
            
        Returns:
            Validated Pydantic model
        """
        from .validators import ParameterValidator
        return ParameterValidator.load_and_validate(parameters_file)


def safe_load_parameters(parameters_file: Union[str, Path]) -> Union[SimulationParameters, Dict[str, Any]]:
    """
    Convenience function for safe parameter loading.
    
    Args:
        parameters_file: Path to parameter file
        
    Returns:
        Either validated Pydantic model or legacy dict
    """
    return BackwardCompatibilityManager.safe_load_parameters(parameters_file)