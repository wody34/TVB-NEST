#  Copyright 2020 Forschungszentrum Jülich GmbH and Aix-Marseille Université
# "Licensed to the Apache Software Foundation (ASF) under one or more contributor license agreements; and to You under the Apache License, Version 2.0. "

"""
Experiment Builder for TVB-NEST co-simulation.

This module implements the Builder pattern for experiment configuration,
making it easier to create and configure complex co-simulation experiments
while maintaining backward compatibility with existing parameter systems.
"""

from pathlib import Path
import types
import logging
import itertools
import copy
from typing import Union, Dict, Any, List, Optional

try:
    from .validation.schemas import SimulationParameters
    from .validation.compatibility import BackwardCompatibilityManager
    from .parameters_manager import generate_parameter, create_linked_parameters
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False


class ExperimentBuilder:
    """
    Builder pattern implementation for TVB-NEST co-simulation experiments.
    
    Provides a fluent interface for configuring complex experiments with
    parameter exploration, validation, and result organization.
    
    Example usage:
        experiment = (ExperimentBuilder()
                     .with_base_parameters(parameter_module)
                     .with_results_path("./my_experiment/")
                     .with_simulation_time(begin=0.0, end=200.0)
                     .explore_parameter("g", [1.0, 1.5, 2.0])
                     .explore_parameter("mean_I_ext", [0.0, 0.1, 0.2])
                     .with_validation(enabled=True)
                     .build())
    """
    
    def __init__(self):
        """Initialize empty experiment builder."""
        self._base_parameters = None
        self._results_path = None
        self._exploration_variables = {}
        self._validation_enabled = True
        self._experiment_name = None
        self._description = None
        self._custom_parameter_links = {}
        # Simulation timing parameters
        self._begin = None
        self._end = None
        
    def with_base_parameters(self, parameters: Union[types.ModuleType, Dict[str, Any], 'SimulationParameters']) -> 'ExperimentBuilder':
        """
        Set base parameters for the experiment.
        
        Args:
            parameters: Module object, dict, or Pydantic model with base parameters
            
        Returns:
            Self for method chaining
        """
        self._base_parameters = parameters
        return self
        
    def with_results_path(self, path: Union[str, Path]) -> 'ExperimentBuilder':
        """
        Set results output path for the experiment.
        
        Args:
            path: Directory path for experiment results
            
        Returns:
            Self for method chaining
        """
        self._results_path = str(Path(path).resolve())
        return self
        
    def explore_parameter(self, parameter_name: str, values: List[Any]) -> 'ExperimentBuilder':
        """
        Add a parameter for exploration with multiple values.
        
        Args:
            parameter_name: Name of parameter to explore
            values: List of values to explore
            
        Returns:
            Self for method chaining
        """
        if parameter_name in self._exploration_variables:
            logging.warning(f"Overriding existing exploration for {parameter_name}")
        self._exploration_variables[parameter_name] = values
        return self
    
    def with_simulation_time(self, begin: float, end: float) -> 'ExperimentBuilder':
        """
        Set simulation time range for the experiment.
        
        Args:
            begin: Start time for simulation (in ms)
            end: End time for simulation (in ms)
            
        Returns:
            Self for method chaining
            
        Raises:
            ValueError: If begin >= end or values are negative
        """
        if begin < 0:
            raise ValueError(f"Begin time must be non-negative, got: {begin}")
        if end <= begin:
            raise ValueError(f"End time ({end}) must be greater than begin time ({begin})")
            
        self._begin = begin
        self._end = end
        return self
        
    def explore_parameters(self, exploration_dict: Dict[str, List[Any]]) -> 'ExperimentBuilder':
        """
        Add multiple parameters for exploration.
        
        Args:
            exploration_dict: Dictionary mapping parameter names to value lists
            
        Returns:
            Self for method chaining
        """
        self._exploration_variables.update(exploration_dict)
        return self
        
    def with_validation(self, enabled: bool = True) -> 'ExperimentBuilder':
        """
        Enable or disable parameter validation.
        
        Args:
            enabled: Whether to enable Pydantic validation
            
        Returns:
            Self for method chaining
        """
        self._validation_enabled = enabled and PYDANTIC_AVAILABLE
        return self
        
    def with_experiment_name(self, name: str) -> 'ExperimentBuilder':
        """
        Set experiment name for organization.
        
        Args:
            name: Human-readable experiment name
            
        Returns:
            Self for method chaining
        """
        self._experiment_name = name
        return self
        
    def with_description(self, description: str) -> 'ExperimentBuilder':
        """
        Set experiment description.
        
        Args:
            description: Detailed experiment description
            
        Returns:
            Self for method chaining
        """
        self._description = description
        return self
        
    def with_custom_parameter_link(self, target_param: str, source_param: str, 
                                 transform_func: Optional[callable] = None) -> 'ExperimentBuilder':
        """
        Add custom parameter linking beyond the default TVB-NEST links.
        
        Args:
            target_param: Target parameter path (e.g., 'param_tvb_model.custom_value')
            source_param: Source parameter path (e.g., 'param_nest.custom_source')
            transform_func: Optional transformation function
            
        Returns:
            Self for method chaining
        """
        self._custom_parameter_links[target_param] = {
            'source': source_param,
            'transform': transform_func or (lambda x: x)
        }
        return self
        
    def validate_configuration(self) -> List[str]:
        """
        Validate the current builder configuration.
        
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        if self._base_parameters is None:
            errors.append("Base parameters not set. Use with_base_parameters()")
            
        if self._results_path is None:
            errors.append("Results path not set. Use with_results_path()")
            
        # Validate exploration parameters
        for param_name, values in self._exploration_variables.items():
            if not isinstance(values, (list, tuple)):
                errors.append(f"Exploration values for '{param_name}' must be a list")
            if len(values) == 0:
                errors.append(f"Exploration values for '{param_name}' cannot be empty")
                
        # Validate results path (directory creation handled in Experiment.__init__)
        if self._results_path:
            try:
                results_dir = Path(self._results_path)
                # Only validate that the path is valid, don't create it
                results_dir.resolve()
            except (OSError, IOError) as e:
                errors.append(f"Invalid results directory path '{self._results_path}': {e}")
                
        return errors
        
    def build(self) -> 'Experiment':
        """
        Build the configured experiment.
        
        Returns:
            Configured Experiment object
            
        Raises:
            ValueError: If configuration is invalid
        """
        # Validate configuration
        errors = self.validate_configuration()
        if errors:
            raise ValueError(f"Invalid experiment configuration:\n" + "\n".join(f"- {error}" for error in errors))
            
        # Create experiment object
        return Experiment(
            base_parameters=self._base_parameters,
            results_path=self._results_path,
            exploration_variables=copy.deepcopy(self._exploration_variables),
            validation_enabled=self._validation_enabled,
            experiment_name=self._experiment_name,
            description=self._description,
            custom_parameter_links=copy.deepcopy(self._custom_parameter_links),
            simulation_begin=self._begin,
            simulation_end=self._end
        )
        
    def quick_exploration(self, parameter_module, results_path: str, 
                         exploration_dict: Dict[str, List[Any]]) -> 'Experiment':
        """
        Quick method to build simple exploration experiments.
        
        Args:
            parameter_module: Base parameter module object
            results_path: Output directory path
            exploration_dict: Parameters to explore
            
        Returns:
            Configured Experiment object
        """
        return (self.with_base_parameters(parameter_module)
                    .with_results_path(results_path)
                    .explore_parameters(exploration_dict)
                    .build())


class Experiment:
    """
    Represents a configured co-simulation experiment.
    
    This class holds the complete experiment configuration and provides
    methods for generating parameter sets and running the experiment.
    """
    
    def __init__(self, base_parameters, results_path: str, exploration_variables: Dict[str, List[Any]],
                 validation_enabled: bool = True, experiment_name: Optional[str] = None,
                 description: Optional[str] = None, custom_parameter_links: Optional[Dict[str, Any]] = None,
                 simulation_begin: Optional[float] = None, simulation_end: Optional[float] = None):
        """
        Initialize experiment with configuration.
        
        Args:
            base_parameters: Base parameter configuration
            results_path: Output directory path
            exploration_variables: Parameters to explore
            validation_enabled: Whether to use Pydantic validation
            experiment_name: Optional experiment name
            description: Optional experiment description
            custom_parameter_links: Optional custom parameter links
            simulation_begin: Optional simulation start time
            simulation_end: Optional simulation end time
        """
        self.base_parameters = base_parameters
        self.results_path = results_path
        self.exploration_variables = exploration_variables
        self.validation_enabled = validation_enabled
        self.experiment_name = experiment_name
        self.description = description
        self.custom_parameter_links = custom_parameter_links or {}
        self.simulation_begin = simulation_begin
        self.simulation_end = simulation_end
        
        # Ensure results directory exists
        Path(self.results_path).mkdir(parents=True, exist_ok=True)
        
    def generate_parameter_sets(self) -> List[Union[Dict[str, Any], 'SimulationParameters']]:
        """
        Generate all parameter sets for the exploration.
        
        Returns:
            List of parameter sets for each exploration combination
        """
        if not self.exploration_variables:
            # No exploration - return single parameter set
            return [self._generate_single_parameter_set({})]
            
        # Generate cartesian product of exploration variables
        parameter_sets = []
        exploration_combinations = self._generate_exploration_combinations()
        
        for combination in exploration_combinations:
            param_set = self._generate_single_parameter_set(combination)
            parameter_sets.append(param_set)
            
        return parameter_sets
        
    def _generate_single_parameter_set(self, exploration_vars: Dict[str, Any]) -> Union[Dict[str, Any], 'SimulationParameters']:
        """
        Generate a single parameter set with exploration variables applied.
        
        Args:
            exploration_vars: Dictionary of exploration variable values
            
        Returns:
            Parameter set (dict or Pydantic model)
        """
        return generate_parameter(
            parameter_default=self.base_parameters,
            results_path=self.results_path,
            dict_variable=exploration_vars if exploration_vars else None
        )
        
    def _generate_exploration_combinations(self) -> List[Dict[str, Any]]:
        """
        Generate all combinations of exploration variables.
        
        Returns:
            List of dictionaries with exploration variable combinations
        """
        
        # Get parameter names and values
        param_names = list(self.exploration_variables.keys())
        param_values = list(self.exploration_variables.values())
        
        # Generate cartesian product
        combinations = []
        for combination in itertools.product(*param_values):
            combo_dict = dict(zip(param_names, combination))
            combinations.append(combo_dict)
            
        return combinations
        
    def get_experiment_info(self) -> Dict[str, Any]:
        """
        Get experiment metadata and configuration.
        
        Returns:
            Dictionary with experiment information
        """
        num_combinations = 1
        for values in self.exploration_variables.values():
            num_combinations *= len(values)
            
        return {
            'name': self.experiment_name,
            'description': self.description,
            'results_path': self.results_path,
            'exploration_variables': self.exploration_variables,
            'num_parameter_combinations': num_combinations,
            'validation_enabled': self.validation_enabled,
            'custom_parameter_links': self.custom_parameter_links
        }
        
    def save_experiment_metadata(self) -> None:
        """Save experiment metadata to results directory."""
        import json
        
        metadata = self.get_experiment_info()
        metadata_file = Path(self.results_path) / 'experiment_metadata.json'
        
        try:
            with metadata_file.open('w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
        except (IOError, OSError) as e:
            logging.error(f"Failed to save experiment metadata: {e}")


# Convenience functions for common experiment patterns

def create_parameter_exploration_experiment(parameter_module, results_path: str, 
                                          exploration_dict: Dict[str, List[Any]]) -> Experiment:
    """
    Create a simple parameter exploration experiment.
    
    Args:
        parameter_module: Base parameter module
        results_path: Output directory
        exploration_dict: Parameters to explore
        
    Returns:
        Configured Experiment object
    """
    return (ExperimentBuilder()
            .quick_exploration(parameter_module, results_path, exploration_dict))


def create_single_run_experiment(parameter_module, results_path: str) -> Experiment:
    """
    Create a single-run experiment without parameter exploration.
    
    Args:
        parameter_module: Base parameter module
        results_path: Output directory
        
    Returns:
        Configured Experiment object
    """
    return (ExperimentBuilder()
            .with_base_parameters(parameter_module)
            .with_results_path(results_path)
            .build())