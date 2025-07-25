#  Copyright 2020 Forschungszentrum Jülich GmbH and Aix-Marseille Université
# "Licensed to the Apache Software Foundation (ASF) under one or more contributor license agreements; and to You under the Apache License, Version 2.0. "

"""
Unit tests for parameter validation schemas.

This module tests Pydantic schema definitions for TVB-NEST parameters,
ensuring proper validation, type checking, and error handling.
"""

import pytest
from pydantic import ValidationError


class TestCoSimulationParams:
    """Test CoSimulationParams schema validation"""
    
    def test_valid_co_simulation_params(self):
        """Test that valid co-simulation parameters are accepted"""
        # This test will fail initially - TDD Red phase
        from nest_elephant_tvb.orchestrator.validation.schemas import CoSimulationParams
        
        valid_params = {
            "co-simulation": True,
            "nb_MPI_nest": 10,
            "level_log": 1,
            "cluster": False
        }
        
        # This should not raise an exception
        params = CoSimulationParams(**valid_params)
        
        # Verify values are correctly assigned
        assert params.co_simulation is True
        assert params.nb_MPI_nest == 10
        assert params.level_log == 1
        assert params.cluster is False
    
    def test_invalid_mpi_process_count(self):
        """Test that invalid MPI process counts are rejected"""
        from nest_elephant_tvb.orchestrator.validation.schemas import CoSimulationParams
        
        invalid_params = {
            "co-simulation": True,
            "nb_MPI_nest": 0,  # Invalid: must be >= 1
            "level_log": 1
        }
        
        with pytest.raises(ValidationError) as exc_info:
            CoSimulationParams(**invalid_params)
        
        # Verify error message mentions the constraint
        assert "nb_MPI_nest" in str(exc_info.value)
        assert "greater than or equal to 1" in str(exc_info.value)
    
    def test_invalid_log_level(self):
        """Test that invalid log levels are rejected"""
        from nest_elephant_tvb.orchestrator.validation.schemas import CoSimulationParams
        
        invalid_params = {
            "co-simulation": True,
            "nb_MPI_nest": 10,
            "level_log": 5  # Invalid: must be 0-4
        }
        
        with pytest.raises(ValidationError) as exc_info:
            CoSimulationParams(**invalid_params)
        
        assert "level_log" in str(exc_info.value)
    
    def test_missing_required_fields(self):
        """Test that missing required fields are detected"""
        from nest_elephant_tvb.orchestrator.validation.schemas import CoSimulationParams
        
        incomplete_params = {
            "nb_MPI_nest": 10
            # Missing required "co-simulation" and "level_log"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            CoSimulationParams(**incomplete_params)
        
        error_str = str(exc_info.value)
        assert "co_simulation" in error_str or "co-simulation" in error_str
        assert "level_log" in error_str
    
    def test_alias_support(self):
        """Test that field aliases work correctly"""
        from nest_elephant_tvb.orchestrator.validation.schemas import CoSimulationParams
        
        # Test with alias "co-simulation"
        params_with_alias = {
            "co-simulation": True,
            "nb_MPI_nest": 10,
            "level_log": 1
        }
        
        params = CoSimulationParams(**params_with_alias)
        assert params.co_simulation is True
        
        # Test with field name "co_simulation"
        params_with_field = {
            "co_simulation": True,
            "nb_MPI_nest": 10,
            "level_log": 1
        }
        
        params = CoSimulationParams(**params_with_field)
        assert params.co_simulation is True


class TestSimulationParameters:
    """Test SimulationParameters root schema validation"""
    
    def test_valid_simulation_parameters(self):
        """Test that valid simulation parameters are accepted"""
        from nest_elephant_tvb.orchestrator.validation.schemas import SimulationParameters
        
        valid_params = {
            "result_path": "/tmp/test_simulation",
            "begin": 0.0,
            "end": 100.0,
            "param_co_simulation": {
                "co-simulation": True,
                "nb_MPI_nest": 10,
                "level_log": 1,
                "cluster": False
            },
            # Required for co-simulation
            "param_TR_nest_to_tvb": {"some": "config"},
            "param_TR_tvb_to_nest": {"some": "config"}
        }
        
        params = SimulationParameters(**valid_params)
        
        assert params.begin == 0.0
        assert params.end == 100.0
        assert params.param_co_simulation.co_simulation is True
    
    def test_end_time_validation(self):
        """Test that end time must be greater than begin time"""
        from nest_elephant_tvb.orchestrator.validation.schemas import SimulationParameters
        
        invalid_params = {
            "result_path": "/tmp/test_simulation",
            "begin": 100.0,
            "end": 50.0,  # Invalid: end < begin
            "param_co_simulation": {
                "co-simulation": True,
                "nb_MPI_nest": 10,
                "level_log": 1
            }
        }
        
        with pytest.raises(ValidationError) as exc_info:
            SimulationParameters(**invalid_params)
        
        assert "end time must be greater than begin time" in str(exc_info.value)
    
    def test_backward_compatibility_extra_fields(self):
        """Test that extra fields are preserved for backward compatibility"""
        from nest_elephant_tvb.orchestrator.validation.schemas import SimulationParameters
        
        params_with_extra = {
            "result_path": "/tmp/test_simulation",
            "begin": 0.0,
            "end": 100.0,
            "param_co_simulation": {
                "co-simulation": True,
                "nb_MPI_nest": 10,
                "level_log": 1
            },
            # Required for co-simulation
            "param_TR_nest_to_tvb": {"some": "config"},
            "param_TR_tvb_to_nest": {"some": "config"},
            # Extra fields that should be preserved
            "param_tvb_model": {"some": "data"},
            "param_nest_topology": {"neurons": 1000},
            "custom_field": "custom_value"
        }
        
        params = SimulationParameters(**params_with_extra)
        
        # Extra fields should be accessible
        assert hasattr(params, 'param_tvb_model')
        assert hasattr(params, 'param_nest_topology')
        assert hasattr(params, 'custom_field')


if __name__ == "__main__":
    pytest.main([__file__])