#  Copyright 2020 Forschungszentrum Jülich GmbH and Aix-Marseille Université
# "Licensed to the Apache Software Foundation (ASF) under one or more contributor license agreements; and to You under the Apache License, Version 2.0. "

"""
Integration tests for parameter validation with existing parameter files.

This module tests the Pydantic validation system against real parameter files
from the TVB-NEST project to ensure backward compatibility and functionality.
"""

import pytest
from pathlib import Path


class TestParameterFileIntegration:
    """Test integration with existing parameter files"""
    
    def test_short_simulation_parameter_file(self):
        """Test validation with the short simulation parameter file"""
        from nest_elephant_tvb.orchestrator.validation import ParameterValidator
        
        param_file = Path("/home/example/short_simulation/parameter.json")
        
        # This should work without errors
        params = ParameterValidator.load_and_validate(param_file)
        
        # Verify key parameters are correctly loaded
        assert params.param_co_simulation.co_simulation is True
        assert params.param_co_simulation.nb_MPI_nest == 10
        assert params.param_co_simulation.level_log == 1
        assert params.begin == 0.0
        assert params.end == 200.0
        
        # Verify backward compatibility - extra fields preserved
        assert hasattr(params, 'param_tvb_model')
        assert hasattr(params, 'param_nest_topology')
        assert hasattr(params, 'param_TR_nest_to_tvb')
    
    def test_parameter_integration_safe_loading(self):
        """Test the safe parameter loading with fallback"""
        from nest_elephant_tvb.orchestrator.validation import ParameterIntegration
        
        param_file = "/home/example/short_simulation/parameter.json"
        
        # This should work and return a dictionary
        params_dict = ParameterIntegration.load_parameters_safe(param_file)
        
        assert isinstance(params_dict, dict)
        assert "param_co_simulation" in params_dict
        assert "result_path" in params_dict
        assert "begin" in params_dict
        assert "end" in params_dict
    
    def test_typed_parameter_access(self):
        """Test type-safe parameter access"""
        from nest_elephant_tvb.orchestrator.validation import ParameterIntegration
        
        param_file = "/home/example/short_simulation/parameter.json"
        
        # Get typed parameters
        params = ParameterIntegration.get_typed_parameters(param_file)
        
        # Test type-safe access (this would give IDE autocompletion)
        mpi_processes = params.param_co_simulation.nb_MPI_nest
        log_level = params.param_co_simulation.level_log
        
        assert isinstance(mpi_processes, int)
        assert isinstance(log_level, int)
        assert 1 <= mpi_processes <= 1000
        assert 0 <= log_level <= 4


class TestValidationPerformance:
    """Test validation performance requirements"""
    
    def test_validation_speed(self):
        """Test that validation completes within performance requirements"""
        import time
        from nest_elephant_tvb.orchestrator.validation import ParameterValidator
        
        param_file = Path("/home/example/short_simulation/parameter.json")
        
        start_time = time.time()
        params = ParameterValidator.load_and_validate(param_file)
        end_time = time.time()
        
        validation_time = end_time - start_time
        
        # Should complete in less than 100ms (requirement)
        assert validation_time < 0.1, f"Validation took {validation_time:.3f}s, should be < 0.1s"
    
    def test_multiple_validations(self):
        """Test performance with multiple validations"""
        import time
        from nest_elephant_tvb.orchestrator.validation import ParameterValidator
        
        param_file = Path("/home/example/short_simulation/parameter.json")
        
        start_time = time.time()
        for _ in range(10):
            params = ParameterValidator.load_and_validate(param_file)
        end_time = time.time()
        
        total_time = end_time - start_time
        avg_time = total_time / 10
        
        # Average should still be fast
        assert avg_time < 0.05, f"Average validation time {avg_time:.3f}s too slow"


if __name__ == "__main__":
    pytest.main([__file__])