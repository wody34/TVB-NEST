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


if __name__ == "__main__":
    pytest.main([__file__])