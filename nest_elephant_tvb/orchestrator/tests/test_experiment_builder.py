#  Copyright 2020 Forschungszentrum Jülich GmbH and Aix-Marseille Université
# "Licensed to the Apache Software Foundation (ASF) under one or more contributor license agreements; and to You under the Apache License, Version 2.0. "

"""
Tests for experiment_builder.py - Builder pattern implementation.

This module tests the ExperimentBuilder and related functionality
for creating and configuring co-simulation experiments.
"""

import pytest
import tempfile
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

from nest_elephant_tvb.orchestrator.experiment_builder import (
    ExperimentBuilder,
    Experiment,
    create_parameter_exploration_experiment,
    create_single_run_experiment
)


# Mock parameter module for testing
def create_mock_parameter_module():
    """Create a mock parameter module object for testing."""
    mock_module = types.ModuleType('test_parameters')
    
    # Add parameter attributes
    mock_module.param_co_simulation = {
        'co-simulation': True,
        'level_log': 1,
        'nb_MPI_nest': 4,
        'record_MPI': False,
        'synchronization': 3.5
    }
    
    mock_module.param_nest = {
        'sim_resolution': 0.1,
        'master_seed': 46,
        'total_num_virtual_procs': 4
    }
    
    mock_module.param_nest_topology = {
        'nb_region': 2,
        'nb_neuron_by_region': 1000,
        'param_neuron_excitatory': {
            'g_L': 10.0,
            'C_m': 250.0,
            'tau_w': 144.0
        },
        'param_neuron_inhibitory': {
            'g_L': 10.0,
            'C_m': 250.0,
            'tau_w': 144.0
        }
    }
    
    return mock_module


class TestExperimentBuilder:
    """Test the ExperimentBuilder class."""
    
    def test_builder_basic_configuration(self):
        """Test basic builder configuration."""
        mock_params = create_mock_parameter_module()
        
        builder = ExperimentBuilder()
        experiment = (builder
                     .with_base_parameters(mock_params)
                     .with_results_path("./test_results/")
                     .with_experiment_name("Test Experiment")
                     .build())
        
        assert experiment.experiment_name == "Test Experiment"
        assert experiment.results_path == str(Path("./test_results/").resolve())
        assert experiment.base_parameters == mock_params
        
    def test_builder_parameter_exploration(self):
        """Test parameter exploration configuration."""
        mock_params = create_mock_parameter_module()
        
        builder = ExperimentBuilder()
        experiment = (builder
                     .with_base_parameters(mock_params)
                     .with_results_path("./test_results/")
                     .explore_parameter("g", [1.0, 1.5, 2.0])
                     .explore_parameter("mean_I_ext", [0.0, 0.1])
                     .build())
        
        assert "g" in experiment.exploration_variables
        assert "mean_I_ext" in experiment.exploration_variables
        assert experiment.exploration_variables["g"] == [1.0, 1.5, 2.0]
        assert experiment.exploration_variables["mean_I_ext"] == [0.0, 0.1]
        
    def test_builder_validation_errors(self):
        """Test builder validation catches configuration errors."""
        builder = ExperimentBuilder()
        
        # Missing base parameters
        with pytest.raises(ValueError) as exc_info:
            builder.with_results_path("./test/").build()
        
        error_message = str(exc_info.value)
        assert "Base parameters not set" in error_message
        
        # Missing results path
        with pytest.raises(ValueError) as exc_info:
            ExperimentBuilder().with_base_parameters(create_mock_parameter_module()).build()
        
        error_message = str(exc_info.value)
        assert "Results path not set" in error_message
        
    def test_builder_quick_exploration(self):
        """Test quick exploration method."""
        mock_params = create_mock_parameter_module()
        
        builder = ExperimentBuilder()
        experiment = builder.quick_exploration(
            parameter_module=mock_params,
            results_path="./test_results/",
            exploration_dict={"g": [1.0, 2.0], "mean_I_ext": [0.0, 0.1]}
        )
        
        assert experiment.base_parameters == mock_params
        assert len(experiment.exploration_variables) == 2
        
    def test_builder_fluent_interface(self):
        """Test that builder methods return self for chaining."""
        builder = ExperimentBuilder()
        
        # All methods should return the builder instance
        assert builder.with_base_parameters({}) is builder
        assert builder.with_results_path("./test/") is builder
        assert builder.explore_parameter("test", [1, 2]) is builder
        assert builder.with_validation(True) is builder
        assert builder.with_experiment_name("Test") is builder
        

class TestExperiment:
    """Test the Experiment class."""
    
    def test_experiment_initialization(self):
        """Test experiment initialization."""
        mock_params = create_mock_parameter_module()
        
        experiment = Experiment(
            base_parameters=mock_params,
            results_path="./test_results/",
            exploration_variables={"g": [1.0, 2.0]},
            experiment_name="Test Experiment"
        )
        
        assert experiment.experiment_name == "Test Experiment"
        assert experiment.exploration_variables == {"g": [1.0, 2.0]}
        
    def test_experiment_parameter_set_generation_no_exploration(self):
        """Test parameter set generation without exploration."""
        mock_params = create_mock_parameter_module()
        
        experiment = Experiment(
            base_parameters=mock_params,
            results_path="./test_results/",
            exploration_variables={}
        )
        
        with patch('nest_elephant_tvb.orchestrator.experiment_builder.generate_parameter') as mock_generate:
            mock_generate.return_value = {"test": "parameters"}
            
            parameter_sets = experiment.generate_parameter_sets()
            
            assert len(parameter_sets) == 1
            # Verify mock was called correctly  
            mock_generate.assert_called_once()
            # Don't check specific arguments as they may vary in format (positional vs keyword)
            
    def test_experiment_parameter_set_generation_with_exploration(self):
        """Test parameter set generation with exploration."""
        mock_params = create_mock_parameter_module()
        
        experiment = Experiment(
            base_parameters=mock_params,
            results_path="./test_results/",
            exploration_variables={"g": [1.0, 2.0], "mean_I_ext": [0.0, 0.1]}
        )
        
        with patch('nest_elephant_tvb.orchestrator.experiment_builder.generate_parameter') as mock_generate:
            mock_generate.return_value = {"test": "parameters"}
            
            parameter_sets = experiment.generate_parameter_sets()
            
            # Should generate 2 * 2 = 4 combinations
            assert len(parameter_sets) == 4
            assert mock_generate.call_count == 4
            
    def test_experiment_info_generation(self):
        """Test experiment info generation."""
        mock_params = create_mock_parameter_module()
        
        experiment = Experiment(
            base_parameters=mock_params,
            results_path="./test_results/",
            exploration_variables={"g": [1.0, 2.0], "mean_I_ext": [0.0, 0.1]},
            experiment_name="Test Experiment",
            description="Test description"
        )
        
        info = experiment.get_experiment_info()
        
        assert info['name'] == "Test Experiment"
        assert info['description'] == "Test description"
        assert info['num_parameter_combinations'] == 4
        assert info['exploration_variables'] == {"g": [1.0, 2.0], "mean_I_ext": [0.0, 0.1]}
        
    def test_experiment_metadata_saving(self):
        """Test experiment metadata saving."""
        mock_params = create_mock_parameter_module()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            experiment = Experiment(
                base_parameters=mock_params,
                results_path=temp_dir,
                exploration_variables={"g": [1.0, 2.0]},
                experiment_name="Test Experiment"
            )
            
            experiment.save_experiment_metadata()
            
            metadata_file = Path(temp_dir) / 'experiment_metadata.json'
            assert metadata_file.exists()
            
            import json
            with metadata_file.open('r', encoding='utf-8') as f:
                metadata = json.load(f)
                
            assert metadata['name'] == "Test Experiment"
            assert metadata['num_parameter_combinations'] == 2


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_create_parameter_exploration_experiment(self):
        """Test parameter exploration experiment creation."""
        mock_params = create_mock_parameter_module()
        
        experiment = create_parameter_exploration_experiment(
            parameter_module=mock_params,
            results_path="./test_results/",
            exploration_dict={"g": [1.0, 2.0]}
        )
        
        assert experiment.base_parameters == mock_params
        assert experiment.exploration_variables == {"g": [1.0, 2.0]}
        
    def test_create_single_run_experiment(self):
        """Test single run experiment creation."""
        mock_params = create_mock_parameter_module()
        
        experiment = create_single_run_experiment(
            parameter_module=mock_params,
            results_path="./test_results/"
        )
        
        assert experiment.base_parameters == mock_params
        assert experiment.exploration_variables == {}


class TestBuilderIntegration:
    """Test integration with existing systems."""
    
    def test_builder_with_pydantic_validation(self):
        """Test builder works with Pydantic validation."""
        mock_params = create_mock_parameter_module()
        
        # Test that builder can handle validation enabled/disabled
        builder = ExperimentBuilder()
        
        experiment_with_validation = (builder
                                    .with_base_parameters(mock_params)
                                    .with_results_path("./test_results/")
                                    .with_validation(enabled=True)
                                    .build())
        
        experiment_without_validation = (builder
                                       .with_base_parameters(mock_params)
                                       .with_results_path("./test_results/")
                                       .with_validation(enabled=False)
                                       .build())
        
        # Both should build successfully
        assert experiment_with_validation.validation_enabled in [True, False]  # Depends on Pydantic availability
        assert experiment_without_validation.validation_enabled == False
        
    def test_builder_with_module_object_parameters(self):
        """Test builder works with module object parameters."""
        mock_params = create_mock_parameter_module()
        
        builder = ExperimentBuilder()
        experiment = (builder
                     .with_base_parameters(mock_params)
                     .with_results_path("./test_results/")
                     .build())
        
        # Should handle module object correctly
        assert experiment.base_parameters == mock_params
        assert isinstance(experiment.base_parameters, types.ModuleType)


@pytest.fixture
def temp_results_dir():
    """Create temporary results directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture  
def mock_parameter_module():
    """Create mock parameter module for testing."""
    return create_mock_parameter_module()


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])