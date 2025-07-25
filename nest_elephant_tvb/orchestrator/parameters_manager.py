#  Copyright 2020 Forschungszentrum Jülich GmbH and Aix-Marseille Université
# "Licensed to the Apache Software Foundation (ASF) under one or more contributor license agreements; and to You under the Apache License, Version 2.0. "

import json
import logging
import numpy as np
import os
import types
from pathlib import Path
from typing import Union, Dict, Any

# Import Pydantic validation components
try:
    from .validation.compatibility import BackwardCompatibilityManager
    from .validation.schemas import SimulationParameters
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False

def generate_parameter(parameter_default, results_path, dict_variable=None):
    """
    Generate parameters for simulation with hybrid Pydantic/legacy support.
    
    This function now supports both:
    1. Module objects (example.parameter.test_nest) → converted to Pydantic
    2. Dictionary parameters → validated with Pydantic
    3. Fallback to legacy behavior if Pydantic unavailable
    
    :param parameter_default: Module object, dict, or Pydantic model with default parameters
    :param results_path: Folder path for simulation results  
    :param dict_variable: Variables to change for parameter exploration
    :return: Parameters ready for simulation (dict or Pydantic model)
    """
    # Try Pydantic-enhanced processing first
    if PYDANTIC_AVAILABLE:
        try:
            return _generate_parameter_pydantic(parameter_default, results_path, dict_variable)
        except (ImportError, AttributeError) as e:
            logging.info(f"Pydantic validation not available or incompatible: {e}")
            logging.info("Falling back to legacy parameter generation")
        except Exception as e:
            logging.warning(f"Pydantic parameter generation failed: {e}")
            logging.info("Falling back to legacy parameter generation")
    
    # Fallback to legacy behavior
    return _generate_parameter_legacy(parameter_default, results_path, dict_variable)


def _generate_parameter_pydantic(parameter_default, results_path, dict_variable=None):
    """
    Enhanced parameter generation with Pydantic validation and module support.
    """
    # Step 1: Convert input to Pydantic model
    if isinstance(parameter_default, types.ModuleType):
        # Handle module objects (critical for run_co-sim.py pattern)
        params = BackwardCompatibilityManager.convert_module_to_pydantic(parameter_default)
    elif hasattr(parameter_default, 'model_dump'):
        # Already a Pydantic model
        params = parameter_default  
    elif isinstance(parameter_default, dict):
        # Dictionary - validate and convert
        from .validation.validators import ParameterValidator
        params = ParameterValidator.validate_dict(parameter_default)
    else:
        raise ValueError(f"Unsupported parameter_default type: {type(parameter_default)}")
    
    # Step 2: Apply exploration variables if provided
    if dict_variable:
        params = BackwardCompatibilityManager.apply_exploration_variables(params, dict_variable)
    
    # Step 3: Create linked parameters (enhanced version)
    return create_linked_parameters(results_path, params)


def _generate_parameter_legacy(parameter_default, results_path, dict_variable=None):
    """
    Original parameter generation logic for fallback compatibility.
    
    This function handles the module object introspection pattern where
    parameter_default is a module (like example.parameter.test_nest) containing
    parameter dictionaries as attributes.
    """
    # Extract all parameter dictionaries from module object
    parameters = {}
    
    # Get all parameter attributes from the module
    for parameters_name in dir(parameter_default):
        if 'param' in parameters_name and not parameters_name.startswith('_'):
            try:
                parameters_values = getattr(parameter_default, parameters_name)
                if isinstance(parameters_values, dict):
                    # Make a deep copy to avoid modifying original module attributes
                    import copy
                    parameters[parameters_name] = copy.deepcopy(parameters_values)
            except AttributeError:
                continue
    
    # Apply exploration variables if provided
    if dict_variable is not None:
        for variable_name, variable_value in dict_variable.items():
            # Search through all parameter sections
            for parameters_name in parameters.keys():
                parameters_values = parameters[parameters_name]
                if isinstance(parameters_values, dict) and variable_name in parameters_values:
                    parameters_values[variable_name] = variable_value
            
            # Handle nested neuron parameters (special case from original code)
            if ('param_nest_topology' in parameters and 
                'param_neuron_excitatory' in parameters['param_nest_topology'] and
                variable_name in parameters['param_nest_topology']['param_neuron_excitatory']):
                parameters['param_nest_topology']['param_neuron_excitatory'][variable_name] = variable_value
            
            # Note: Inhibitory neuron parameters commented out in original due to TODO
            # This preserves the exact behavior of the original implementation
    
    return create_linked_parameters(results_path, parameters)


def create_linked_parameters(results_path, parameters):
    """
    Create linked parameters with hybrid Pydantic/legacy support.
    
    This function now handles both:
    1. Pydantic models → convert to dict, process, optionally convert back
    2. Legacy dictionaries → process as before
    3. Maintains Jupyter notebook compatibility
    
    :param results_path: folder to save the result
    :param parameters: dictionary or Pydantic model of parameters
    :return: processed parameters (dict or Pydantic model)
    """
    # Determine input type and convert to dict for processing
    is_pydantic = hasattr(parameters, 'model_dump')
    
    if is_pydantic:
        # Pydantic model - convert to dict
        param_dict = parameters.model_dump()
        logging.debug("Processing Pydantic model parameters")
    else:
        # Legacy dict
        param_dict = parameters
        logging.debug("Processing legacy dictionary parameters")
    
    # Apply original linking logic to dictionary
    linked_dict = _create_linked_parameters_dict(results_path, param_dict)
    
    # Return in same format as input
    if is_pydantic and PYDANTIC_AVAILABLE:
        try:
            # Convert back to Pydantic model
            from .validation.validators import ParameterValidator
            return ParameterValidator.validate_dict(linked_dict)
        except Exception as e:
            logging.warning(f"Could not convert back to Pydantic model: {e}")
            return linked_dict
    else:
        # Return as dict (legacy or fallback)
        return linked_dict


def _create_linked_parameters_dict(results_path, parameters):
    """
    Original parameter linking logic extracted for reuse.
    
    This function contains the complex parameter linking logic that establishes
    relationships between TVB and NEST parameters, ensuring consistency across
    the co-simulation.
    """
    import copy
    # Make a deep copy to avoid modifying the original nested dictionaries
    parameters = copy.deepcopy(parameters)
    
    param_co_simulation = parameters['param_co_simulation']
    param_nest = parameters['param_nest']
    param_nest_connection = parameters['param_nest_connection']
    param_nest_topology = parameters['param_nest_topology']
    param_tvb_model = parameters['param_tvb_model']

    # link between parameter in nest :
    param_nest_background = parameters['param_nest_background']
    param_nest_background['weight_poisson'] = param_nest_connection['weight_local']
    parameters['param_nest_background'] = param_nest_background

    # link between parameter of TVB and parameter of NEST :

    ## connection
    param_tvb_connection = parameters['param_tvb_connection']
    param_tvb_connection['path_distance'] =  param_nest_connection['path_distance']
    param_tvb_connection['path_weight'] =  param_nest_connection['path_weight']
    param_tvb_connection['nb_region'] =  param_nest_topology['nb_region']
    param_tvb_connection['velocity'] =  param_nest_connection['velocity']
    parameters['param_tvb_connection'] = param_tvb_connection

    ## coupling
    param_tvb_coupling = parameters['param_tvb_coupling']
    param_tvb_coupling['a'] = param_nest_connection['weight_global']
    parameters['param_tvb_coupling'] = param_tvb_coupling

    ## integrator and noise
    param_tvb_integrator = parameters['param_tvb_integrator']
    param_tvb_integrator['sim_resolution'] = param_nest['sim_resolution']
    param_tvb_integrator['seed'] = param_nest['master_seed']-1
    param_tvb_integrator['seed_init'] = param_nest['master_seed']-2
    parameters['param_tvb_integrator'] = param_tvb_integrator

    ## parameter of the model
    param_tvb_model['g_L']=param_nest_topology['param_neuron_excitatory']['g_L']
    param_tvb_model['E_L_e']=param_nest_topology['param_neuron_excitatory']['E_L']
    param_tvb_model['E_L_i']=param_nest_topology['param_neuron_inhibitory']['E_L']
    param_tvb_model['C_m']=param_nest_topology['param_neuron_excitatory']['C_m']
    param_tvb_model['b_e']=param_nest_topology['param_neuron_excitatory']['b']
    param_tvb_model['a_e']=param_nest_topology['param_neuron_excitatory']['a']
    param_tvb_model['b_i']=param_nest_topology['param_neuron_inhibitory']['b']
    param_tvb_model['a_i']=param_nest_topology['param_neuron_inhibitory']['a']
    param_tvb_model['tau_w_e']=param_nest_topology['param_neuron_excitatory']['tau_w']
    param_tvb_model['tau_w_i']=param_nest_topology['param_neuron_inhibitory']['tau_w']
    param_tvb_model['E_e']=param_nest_topology['param_neuron_excitatory']['E_ex']
    param_tvb_model['E_i']=param_nest_topology['param_neuron_excitatory']['E_in']
    param_tvb_model['Q_e']=param_nest_connection['weight_local']
    param_tvb_model['Q_i']=param_nest_connection['weight_local']*param_nest_connection['g']
    param_tvb_model['tau_e']=param_nest_topology['param_neuron_excitatory']['tau_syn_ex']
    param_tvb_model['tau_i']=param_nest_topology['param_neuron_excitatory']['tau_syn_in']
    param_tvb_model['N_tot']=param_nest_topology['nb_neuron_by_region']
    param_tvb_model['p_connect']=param_nest_connection['p_connect']
    param_tvb_model['g']=param_nest_topology['percentage_inhibitory']
    param_tvb_model['K_ext_e']=param_nest_connection['nb_external_synapse']
    parameters['param_tvb_model'] = param_tvb_model

    ## monitor
    param_tvb_monitor = parameters['param_tvb_monitor']
    param_tvb_monitor['parameter_TemporalAverage']['period'] = param_nest['sim_resolution']*10.0
    param_tvb_monitor['parameter_Bold']['period'] = param_nest['sim_resolution']*20000.0
    parameters['param_tvb_monitor'] = param_tvb_monitor

    # Parameter for the translators
    if param_co_simulation['co-simulation']:
        # parameters for the translation TVB to Nest
        if 'param_TR_tvb_to_nest' in parameters.keys():
            param_TR_tvb_to_nest = parameters['param_TR_tvb_to_nest']
        else:
            param_TR_tvb_to_nest = {}
        if not 'init' in param_TR_tvb_to_nest.keys():
            path_rates = Path(results_path) / 'init_rates.npy'
            init_rates = np.array([[] for i in range(param_nest_topology['nb_neuron_by_region'])])
            np.save(str(path_rates), init_rates)
            param_TR_tvb_to_nest['init'] = str(path_rates)
        param_TR_tvb_to_nest['level_log']= param_co_simulation['level_log']
        param_TR_tvb_to_nest['seed'] = param_nest['master_seed']-3
        param_TR_tvb_to_nest['nb_synapses'] = param_nest_connection['nb_external_synapse']
        parameters['param_TR_tvb_to_nest'] = param_TR_tvb_to_nest

        # parameters for the translation nest to TVB
        if 'param_TR_nest_to_tvb' in parameters.keys():
            param_TR_nest_to_tvb = parameters['param_TR_nest_to_tvb']
        else:
            param_TR_nest_to_tvb = {}
        if not 'init' in param_TR_nest_to_tvb.keys():
            path_spikes = Path(results_path) / 'init_spikes.npy'
            init_spikes = np.zeros((int(param_co_simulation['synchronization']/param_nest['sim_resolution']),1))
            np.save(str(path_spikes), init_spikes)
            param_TR_nest_to_tvb['init'] = str(path_spikes)
        param_TR_nest_to_tvb['resolution']=param_nest['sim_resolution']
        param_TR_nest_to_tvb['nb_neurons']=param_nest_topology['nb_neuron_by_region'] * (1-param_nest_topology['percentage_inhibitory'])
        param_TR_nest_to_tvb['synch']=param_co_simulation['synchronization']
        param_TR_nest_to_tvb['width']=param_tvb_model['T']
        param_TR_nest_to_tvb['level_log']= param_co_simulation['level_log']
        parameters['param_TR_nest_to_tvb']= param_TR_nest_to_tvb

    if param_co_simulation['record_MPI']:
        if 'param_record_MPI' in parameters.keys():
            param_record_MPI = parameters['param_record_MPI']
        else:
            param_record_MPI = {}
        param_record_MPI['resolution']=param_nest['sim_resolution']
        param_record_MPI['synch']=param_co_simulation['synchronization']
        param_record_MPI['level_log']= param_co_simulation['level_log']
        parameters['param_record_MPI']= param_record_MPI

    return parameters


def save_parameter(parameters, results_path, begin, end):
    """
    save the parameters of the simulations in json file
    :param parameters: dictionary of parameters or Pydantic model
    :param results_path: where to save the result
    :param begin: when start the recording simulation ( not take in count for tvb (start always to zeros )
    :param end:  when end the recording simulation and the simulation
    :return: nothing
    """
    # save the value of all parameters using pathlib
    results_dir = Path(results_path)
    parameter_file = results_dir / 'parameter.json'
    
    # Convert Pydantic model to dict if necessary
    if PYDANTIC_AVAILABLE and BackwardCompatibilityManager.is_pydantic_model(parameters):
        parameters_dict = parameters.model_dump()
        logging.debug("Converting Pydantic model to dict for saving")
    else:
        parameters_dict = parameters
    
    # Create complete parameter dictionary
    complete_parameters = {
        **parameters_dict,
        "result_path": str(results_dir.resolve()) + "/",
        "begin": begin,
        "end": end
    }
    
    # Use context manager and proper JSON serialization
    try:
        with parameter_file.open("w", encoding="utf-8") as f:
            json.dump(complete_parameters, f, indent=2, ensure_ascii=False)
    except (IOError, OSError) as e:
        logging.error(f"Failed to save parameters to {parameter_file}: {e}")
        raise