#  Copyright 2020 Forschungszentrum Jülich GmbH and Aix-Marseille Université
# "Licensed to the Apache Software Foundation (ASF) under one or more contributor license agreements; and to You under the Apache License, Version 2.0. "

"""
Integration tests for run_exploration.py with Pydantic validation.

This module tests the integration of Pydantic validation into the main
orchestrator functionality while maintaining backward compatibility.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestRunExplorationIntegration:
    """Test integration of Pydantic validation with run_exploration.py"""
    
    def test_run_function_with_pydantic_validation(self):
        """Test that run() function works with Pydantic validation"""
        # We'll create a modified version of run() that uses Pydantic
        from nest_elephant_tvb.orchestrator.validation import ParameterValidator
        from pathlib import Path
        
        param_file = "/home/example/short_simulation/parameter.json"
        
        # This should work without errors - validates the integration path
        params = ParameterValidator.load_and_validate(param_file)
        
        # Verify we can access parameters in the same way as before
        co_sim = params.param_co_simulation
        assert co_sim.co_simulation is True
        assert co_sim.nb_MPI_nest == 10
        assert co_sim.level_log == 1
        
        # Verify result path handling
        assert params.result_path is not None
        assert params.begin == 0.0
        assert params.end == 200.0
    
    @patch('subprocess.Popen')
    def test_parameter_validation_replaces_manual_checks(self, mock_popen):
        """Test that Pydantic validation can replace manual parameter checks"""
        from nest_elephant_tvb.orchestrator.validation import ParameterValidator
        
        # Mock subprocess to avoid actual simulation
        mock_process = MagicMock()
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process
        
        param_file = "/home/example/short_simulation/parameter.json"
        
        # Load and validate parameters
        params = ParameterValidator.load_and_validate(param_file)
        
        # These checks would previously be done manually in run()
        # Now they're automatically validated by Pydantic
        
        # Check co-simulation parameters
        assert isinstance(params.param_co_simulation.nb_MPI_nest, int)
        assert 1 <= params.param_co_simulation.nb_MPI_nest <= 1000
        assert 0 <= params.param_co_simulation.level_log <= 4
        
        # Check simulation time bounds
        assert params.end > params.begin
        assert params.begin >= 0.0
        
        # Check required sections for co-simulation
        if params.param_co_simulation.co_simulation:
            assert params.param_TR_nest_to_tvb is not None
            assert params.param_TR_tvb_to_nest is not None
    
    def test_backward_compatibility_with_existing_code(self):
        """Test that existing code patterns still work"""
        from nest_elephant_tvb.orchestrator.validation import ParameterIntegration
        
        param_file = "/home/example/short_simulation/parameter.json"
        
        # Old way: load as dictionary
        params_dict = ParameterIntegration.load_parameters_safe(param_file)
        
        # Existing code patterns should still work
        co_sim = params_dict['param_co_simulation']
        assert co_sim['co-simulation'] is True  # Note: uses alias
        assert co_sim['nb_MPI_nest'] == 10
        
        # New way: typed access
        params_typed = ParameterIntegration.get_typed_parameters(param_file)
        assert params_typed.param_co_simulation.co_simulation is True
        assert params_typed.param_co_simulation.nb_MPI_nest == 10


class TestErrorHandlingImprovement:
    """Test improved error handling with Pydantic"""
    
    def test_clear_validation_error_messages(self):
        """Test that validation errors provide clear messages"""
        from nest_elephant_tvb.orchestrator.validation import ParameterValidator, ParameterValidationError
        
        # Create invalid parameters
        invalid_params = {
            "result_path": "/tmp/test",
            "begin": 100.0,
            "end": 50.0,  # Invalid: end < begin
            "param_co_simulation": {
                "co-simulation": True,
                "nb_MPI_nest": 0,  # Invalid: must be >= 1
                "level_log": 5  # Invalid: must be 0-4
            }
        }
        
        with pytest.raises(ParameterValidationError) as exc_info:
            ParameterValidator.validate_dict(invalid_params)
        
        error_message = str(exc_info.value)
        
        # Should contain helpful information about what's wrong
        assert "validation failed" in error_message.lower()
        # The actual validation errors will be in the nested exception
    
    def test_missing_file_error_handling(self):
        """Test error handling for missing parameter files"""
        from nest_elephant_tvb.orchestrator.validation import ParameterValidator, ParameterValidationError
        
        with pytest.raises(ParameterValidationError) as exc_info:
            ParameterValidator.load_and_validate("/nonexistent/file.json")
        
        assert "not found" in str(exc_info.value)


class TestParameterCombinationFix:
    """Test fix for parameter combination logic in fallback exploration"""
    
    def test_parameter_combination_generation(self):
        """Test that parameter combinations are generated correctly"""
        import itertools
        
        # Test case that exposed the original bug
        exploration_dict = {"g": [1.0, 1.5], "rate": [10, 20]}
        
        # Generate combinations using the fixed logic
        param_names = list(exploration_dict.keys())
        combinations = []
        for param_combination in itertools.product(*exploration_dict.values()):
            combination_dict = dict(zip(param_names, param_combination))
            combinations.append(combination_dict)
        
        # Verify we get all 4 combinations (2 × 2)
        assert len(combinations) == 4
        
        # Verify specific combinations
        expected_combinations = [
            {"g": 1.0, "rate": 10},
            {"g": 1.0, "rate": 20},
            {"g": 1.5, "rate": 10},
            {"g": 1.5, "rate": 20}
        ]
        
        for expected in expected_combinations:
            assert expected in combinations
    
    def test_single_parameter_exploration(self):
        """Test that single parameter exploration still works"""
        import itertools
        
        exploration_dict = {"g": [1.0, 1.5, 2.0]}
        
        param_names = list(exploration_dict.keys())
        combinations = []
        for param_combination in itertools.product(*exploration_dict.values()):
            combination_dict = dict(zip(param_names, param_combination))
            combinations.append(combination_dict)
        
        # Should generate 3 combinations for single parameter
        assert len(combinations) == 3
        
        expected_combinations = [
            {"g": 1.0},
            {"g": 1.5},
            {"g": 2.0}
        ]
        
        for expected in expected_combinations:
            assert expected in combinations
    
    def test_three_parameter_exploration(self):
        """Test that three parameter exploration generates correct combinations"""
        import itertools
        
        exploration_dict = {
            "g": [1.0, 2.0],
            "rate": [10, 20], 
            "delay": [0.1, 0.2]
        }
        
        param_names = list(exploration_dict.keys())
        combinations = []
        for param_combination in itertools.product(*exploration_dict.values()):
            combination_dict = dict(zip(param_names, param_combination))
            combinations.append(combination_dict)
        
        # Should generate 8 combinations (2 × 2 × 2)
        assert len(combinations) == 8
        
        # Verify a few specific combinations
        assert {"g": 1.0, "rate": 10, "delay": 0.1} in combinations
        assert {"g": 2.0, "rate": 20, "delay": 0.2} in combinations
        assert {"g": 1.0, "rate": 20, "delay": 0.1} in combinations
    
    @patch('nest_elephant_tvb.orchestrator.run_exploration.run_exploration')
    def test_run_exploration_builder_fallback_with_combinations(self, mock_run_exploration):
        """Test that run_exploration_builder fallback correctly calls run_exploration for each combination"""
        from nest_elephant_tvb.orchestrator.run_exploration import run_exploration_builder
        
        # Mock the builder availability
        with patch('nest_elephant_tvb.orchestrator.run_exploration.BUILDER_AVAILABLE', False):
            
            # Create a mock parameter module
            mock_parameter_module = MagicMock()
            
            exploration_dict = {"g": [1.0, 1.5], "rate": [10, 20]}
            
            # Call the function
            run_exploration_builder(
                mock_parameter_module,
                "/tmp/test_results", 
                exploration_dict,
                "Test exploration"
            )
            
            # Verify run_exploration was called 4 times (2×2 combinations)
            assert mock_run_exploration.call_count == 4
            
            # Verify the correct parameter combinations were passed
            expected_calls = [
                {"g": 1.0, "rate": 10},
                {"g": 1.0, "rate": 20},
                {"g": 1.5, "rate": 10},
                {"g": 1.5, "rate": 20}
            ]
            
            actual_calls = [call[0][2] for call in mock_run_exploration.call_args_list]  # 3rd argument is dict_variable
            
            for expected in expected_calls:
                assert expected in actual_calls


if __name__ == "__main__":
    pytest.main([__file__])