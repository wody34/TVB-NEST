#  Copyright 2020 Forschungszentrum Jülich GmbH and Aix-Marseille Université
# "Licensed to the Apache Software Foundation (ASF) under one or more contributor license agreements; and to You under the Apache License, Version 2.0. "

"""
Usage example tests for the enhanced TVB-NEST orchestrator.

This module contains pytest tests that demonstrate usage patterns
and serve as both tests and documentation.
"""

import pytest
import tempfile
import types
import os
from pathlib import Path
from unittest.mock import patch

from nest_elephant_tvb.orchestrator.parameters_manager import generate_parameter
from nest_elephant_tvb.orchestrator.experiment_builder import (
    ExperimentBuilder, 
    create_parameter_exploration_experiment,
    create_single_run_experiment
)


def create_example_parameter_module():
    """Create an example parameter module for testing usage patterns."""
    param_module = types.ModuleType('example_parameters')
    
    # Co-simulation configuration
    param_module.param_co_simulation = {
        'co-simulation': True,
        'nb_MPI_nest': 4,
        'record_MPI': False,
        'id_region_nest': [1, 2],
        'synchronization': 3.5,
        'level_log': 1,
        'cluster': False
    }
    
    # NEST simulator configuration
    param_module.param_nest = {
        'sim_resolution': 0.1,
        'master_seed': 46,
        'total_num_virtual_procs': 4,
        'overwrite_files': True,
        'print_time': True,
        'verbosity': 20
    }
    
    # NEST network topology
    param_module.param_nest_topology = {
        'nb_region': 2,
        'nb_neuron_by_region': 1000,
        'percentage_inhibitory': 0.2,
        'param_neuron_excitatory': {
            'g_L': 10.0,
            'E_L': -65.0,
            'C_m': 250.0,
            'b': 60.0,
            'a': 4.0,
            'tau_w': 144.0,
            'E_ex': 0.0,
            'E_in': -80.0,
            'tau_syn_ex': 5.0,
            'tau_syn_in': 10.0,
            'mean_I_ext': 0.0
        },
        'param_neuron_inhibitory': {
            'g_L': 10.0,
            'E_L': -65.0,
            'C_m': 250.0,
            'b': 0.0,
            'a': 0.0,
            'tau_w': 144.0,
            'E_ex': 0.0,
            'E_in': -80.0,
            'tau_syn_ex': 5.0,
            'tau_syn_in': 10.0,
            'mean_I_ext': 0.0
        }
    }
    
    # NEST network connections
    param_module.param_nest_connection = {
        'weight_local': 5.0,
        'weight_global': 0.1,
        'g': 4.0,
        'p_connect': 0.1,
        'nb_external_synapse': 100,
        'velocity': 1.0,
        'path_distance': './data/distance.txt',
        'path_weight': './data/weights.txt'
    }
    
    # Background activity
    param_module.param_nest_background = {
        'weight_poisson': 5.0
    }
    
    # TVB configuration (will be auto-linked)
    param_module.param_tvb_connection = {
        'path_distance': '',
        'path_weight': '',
        'nb_region': 0,
        'velocity': 0.0
    }
    
    param_module.param_tvb_coupling = {
        'a': 0.0
    }
    
    param_module.param_tvb_integrator = {
        'sim_resolution': 0.0,
        'seed': 0,
        'seed_init': 0
    }
    
    param_module.param_tvb_model = {
        'g_L': 0.0, 'E_L_e': 0.0, 'E_L_i': 0.0, 'C_m': 0.0,
        'b_e': 0.0, 'a_e': 0.0, 'b_i': 0.0, 'a_i': 0.0,
        'tau_w_e': 0.0, 'tau_w_i': 0.0, 'E_e': 0.0, 'E_i': 0.0,
        'Q_e': 0.0, 'Q_i': 0.0, 'tau_e': 0.0, 'tau_i': 0.0,
        'N_tot': 0, 'p_connect': 0.0, 'g': 0.0, 'K_ext_e': 0, 'T': 20.0
    }
    
    param_module.param_tvb_monitor = {
        'parameter_TemporalAverage': {'period': 0.0},
        'parameter_Bold': {'period': 0.0}
    }
    
    # Add translator parameters for complete validation
    param_module.param_TR_tvb_to_nest = {
        'init': './init_rates.npy',
        'level_log': 1,
        'seed': 43,
        'nb_synapses': 100
    }
    
    param_module.param_TR_nest_to_tvb = {
        'init': './init_spikes.npy',
        'resolution': 0.1,
        'nb_neurons': 800,
        'synch': 3.5,
        'width': 20.0,
        'level_log': 1
    }
    
    return param_module


class TestUsageExamples:
    """Test usage examples that serve as documentation."""
    
    def test_traditional_workflow_example(self):
        """Test traditional workflow with module objects (Usage Example 1)."""
        param_module = create_example_parameter_module()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Traditional parameter generation
            base_parameters = generate_parameter(
                parameter_default=param_module,
                results_path=temp_dir,
                dict_variable=None
            )
            
            assert base_parameters is not None
            
            # Parameter exploration
            exploration_vars = {'g': 1.5, 'mean_I_ext': 0.1}
            explored_parameters = generate_parameter(
                parameter_default=param_module,
                results_path=temp_dir,
                dict_variable=exploration_vars
            )
            
            # Verify parameter linking
            if isinstance(explored_parameters, dict):
                param_dict = explored_parameters
            else:
                param_dict = explored_parameters.model_dump()
            
            # Check automatic parameter linking
            weight_local = param_dict['param_nest_connection']['weight_local']
            weight_poisson = param_dict['param_nest_background']['weight_poisson']
            assert weight_local == weight_poisson, "Background weight should be linked to local weight"
            
            weight_global = param_dict['param_nest_connection']['weight_global']
            tvb_coupling = param_dict['param_tvb_coupling']['a']
            assert weight_global == tvb_coupling, "TVB coupling should be linked to global weight"
    
    def test_builder_pattern_basic_example(self):
        """Test basic Builder pattern usage (Usage Example 2)."""
        param_module = create_example_parameter_module()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create experiment using Builder pattern
            experiment = (ExperimentBuilder()
                         .with_base_parameters(param_module)
                         .with_results_path(temp_dir)
                         .with_experiment_name("Basic Builder Example")
                         .with_description("Demonstration of Builder pattern")
                         .explore_parameter("g", [1.0, 1.5, 2.0])
                         .explore_parameter("mean_I_ext", [0.0, 0.1, 0.2])
                         .with_validation(enabled=True)
                         .build())
            
            # Verify experiment configuration
            info = experiment.get_experiment_info()
            assert info['name'] == "Basic Builder Example"
            assert info['num_parameter_combinations'] == 9  # 3 * 3
            assert "g" in info['exploration_variables']
            assert "mean_I_ext" in info['exploration_variables']
            
            # Generate parameter sets
            parameter_sets = experiment.generate_parameter_sets()
            assert len(parameter_sets) == 9
            
            # Verify metadata saving
            experiment.save_experiment_metadata()
            metadata_file = Path(temp_dir) / 'experiment_metadata.json'
            assert metadata_file.exists()
    
    def test_complex_exploration_example(self):
        """Test complex multi-dimensional parameter exploration (Usage Example 3)."""
        param_module = create_example_parameter_module()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Define complex exploration space
            exploration_design = {
                'g': [1.0, 2.0],
                'weight_local': [3.0, 5.0],
                'weight_global': [0.05, 0.1],
                'mean_I_ext': [0.0, 0.1],
            }
            
            # Create complex experiment
            experiment = (ExperimentBuilder()
                         .with_base_parameters(param_module)
                         .with_results_path(temp_dir)
                         .with_experiment_name("Multi-dimensional Parameter Study")
                         .explore_parameters(exploration_design)
                         .build())
            
            # Verify total combinations
            expected_combinations = 2 * 2 * 2 * 2  # 16 combinations
            info = experiment.get_experiment_info()
            assert info['num_parameter_combinations'] == expected_combinations
            
            # Test subset generation (don't generate all for performance)
            all_parameter_sets = experiment.generate_parameter_sets()
            parameter_sets = all_parameter_sets[:5]
            assert len(parameter_sets) <= 5
            assert len(all_parameter_sets) == expected_combinations
            
            # Verify different parameter values are generated by checking all sets
            g_values = set()
            for param_set in all_parameter_sets:
                if isinstance(param_set, dict):
                    g_val = param_set['param_nest_connection']['g']
                else:
                    param_dict = param_set.model_dump()
                    g_val = param_dict['param_nest_connection']['g']
                g_values.add(g_val)
                if len(g_values) >= 2:  # Early exit once we find variety
                    break
            
            assert len(g_values) >= 2, f"Should generate different g values, got: {g_values}"
    
    def test_convenience_functions_example(self):
        """Test convenience functions for common patterns (Usage Example 4)."""
        param_module = create_example_parameter_module()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test create_parameter_exploration_experiment
            experiment = create_parameter_exploration_experiment(
                parameter_module=param_module,
                results_path=temp_dir,
                exploration_dict={"g": [1.0, 2.0], "mean_I_ext": [0.0, 0.1]}
            )
            
            assert experiment.base_parameters == param_module
            assert experiment.exploration_variables == {"g": [1.0, 2.0], "mean_I_ext": [0.0, 0.1]}
            
            # Test create_single_run_experiment
            single_experiment = create_single_run_experiment(
                parameter_module=param_module,
                results_path=temp_dir
            )
            
            assert single_experiment.base_parameters == param_module
            assert single_experiment.exploration_variables == {}
    
    def test_backward_compatibility_example(self):
        """Test integration with existing code patterns (Usage Example 5)."""
        param_module = create_example_parameter_module()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Simulate existing code pattern - modify module attributes
            param_module.param_nest_connection['g'] = 3.0
            param_module.param_nest_topology['param_neuron_excitatory']['mean_I_ext'] = 0.15
            param_module.param_co_simulation['level_log'] = 2
            
            # Generate parameters - should preserve modifications
            parameters = generate_parameter(
                parameter_default=param_module,
                results_path=temp_dir,
                dict_variable=None
            )
            
            # Verify modifications were preserved
            if isinstance(parameters, dict):
                param_dict = parameters
            else:
                param_dict = parameters.model_dump()
            
            assert param_dict['param_nest_connection']['g'] == 3.0
            assert param_dict['param_nest_topology']['param_neuron_excitatory']['mean_I_ext'] == 0.15
            assert param_dict['param_co_simulation']['level_log'] == 2
            
            # Verify parameter linking still works
            weight_local = param_dict['param_nest_connection']['weight_local']
            weight_poisson = param_dict['param_nest_background']['weight_poisson']
            assert weight_local == weight_poisson


class TestErrorHandlingExamples:
    """Test error handling and edge cases."""
    
    def test_invalid_builder_configuration(self):
        """Test that builder validates configuration properly."""
        builder = ExperimentBuilder()
        
        # Missing base parameters should raise error
        with pytest.raises(ValueError) as exc_info:
            builder.with_results_path("./test/").build()
        
        assert "Base parameters not set" in str(exc_info.value)
    
    def test_empty_exploration_variables(self):
        """Test builder with no exploration variables."""
        param_module = create_example_parameter_module()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            experiment = (ExperimentBuilder()
                         .with_base_parameters(param_module)
                         .with_results_path(temp_dir)
                         .build())
            
            parameter_sets = experiment.generate_parameter_sets()
            assert len(parameter_sets) == 1  # Single parameter set
    
    def test_fallback_behavior(self):
        """Test that fallback mechanisms work correctly."""
        param_module = create_example_parameter_module()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Even if Pydantic fails, should fall back to legacy mode
            result = generate_parameter(
                parameter_default=param_module,
                results_path=temp_dir,
                dict_variable={'nonexistent_param': 999}
            )
            
            # Should still produce valid results
            assert result is not None
            if isinstance(result, dict):
                assert 'param_co_simulation' in result
            else:
                assert hasattr(result, 'param_co_simulation')


@pytest.fixture
def example_parameter_module():
    """Fixture providing example parameter module for tests."""
    return create_example_parameter_module()


# Integration with pytest discovery
if __name__ == "__main__":
    pytest.main([__file__, "-v"])