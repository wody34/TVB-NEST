#  Copyright 2020 Forschungszentrum Jülich GmbH and Aix-Marseille Université
# "Licensed to the Apache Software Foundation (ASF) under one or more contributor license agreements; and to You under the Apache License, Version 2.0. "

import datetime
import os
import sys
import json
import subprocess
import logging
import time
import numpy as np
from pathlib import Path
from nest_elephant_tvb.orchestrator.parameters_manager import generate_parameter,save_parameter
from nest_elephant_tvb.orchestrator.validation.compatibility import safe_load_parameters, BackwardCompatibilityManager

# Import Builder pattern (optional - for enhanced experiment configuration)
try:
    from nest_elephant_tvb.orchestrator.experiment_builder import (
        ExperimentBuilder, 
        create_parameter_exploration_experiment,
        create_single_run_experiment
    )
    BUILDER_AVAILABLE = True
except ImportError:
    BUILDER_AVAILABLE = False

def ensure_directories(base_path, subdirs):
    """
    Create directories using pathlib with proper error handling
    
    Args:
        base_path: Base directory path (str or Path)
        subdirs: List of subdirectory names to create
    """
    base = Path(base_path)
    
    try:
        # Create base directory first
        base.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        for subdir in subdirs:
            dir_path = base / subdir
            dir_path.mkdir(parents=True, exist_ok=True)
            
    except (OSError, IOError) as e:
        logging.warning(f"Failed to create some directories: {e}")

def run(parameters_file):
    '''
    run the simulation
    :param parameters_file: parameters of the simulation
    :return:
    '''
    # 🚀 NEW: Load and validate parameters with Pydantic (with fallback)
    # Replaces 25+ lines of manual validation with 1 line + compatibility layer
    parameters = safe_load_parameters(parameters_file)
    
    # Create result directories using pathlib
    # Get result path using compatibility layer
    result_path_str = BackwardCompatibilityManager.get_parameter_value(parameters, 'result_path')
    results_path = Path.cwd() / result_path_str
    base_dirs = ['log', 'nest', 'tvb']
    ensure_directories(results_path, base_dirs)

    # Get co-simulation parameters using compatibility layer
    if BackwardCompatibilityManager.is_pydantic_model(parameters):
        param_co_simulation = parameters.param_co_simulation
        # Convert to dict for existing code compatibility (use by_alias to preserve field names)
        param_co_simulation = param_co_simulation.model_dump(by_alias=True)
    else:
        param_co_simulation = parameters['param_co_simulation']

    # configuration of the logger
    level_log = param_co_simulation['level_log']
    logger = logging.getLogger('orchestrator')
    fh = logging.FileHandler(str(results_path / 'log' / 'orchestrator.log'))
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    if level_log == 0:
        fh.setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
    elif  level_log == 1:
        fh.setLevel(logging.INFO)
        logger.setLevel(logging.INFO)
    elif  level_log == 2:
        fh.setLevel(logging.WARNING)
        logger.setLevel(logging.WARNING)
    elif  level_log == 3:
        fh.setLevel(logging.ERROR)
        logger.setLevel(logging.ERROR)
    elif  level_log == 4:
        fh.setLevel(logging.CRITICAL)
        logger.setLevel(logging.CRITICAL)

    logger.info('time: '+str(datetime.datetime.now())+' BEGIN SIMULATION \n')

    # chose between running on cluster or local pc
    if param_co_simulation['cluster']:
        mpirun = 'srun'
    else:
        mpirun = 'mpirun'

    processes = [] # process generate for the co-simulation
    if param_co_simulation['co-simulation']:
        # First case : co-simulation
        # Create translation directories using pathlib
        translation_dirs = [
            Path('translation/spike_detector'),
            Path('translation/send_to_tvb'), 
            Path('translation/spike_generator'),
            Path('translation/receive_from_tvb')
        ]
        ensure_directories(results_path, translation_dirs)

        id_proxy = param_co_simulation['id_region_nest']

        #Run Nest and take information for the connection between all the mpi process
        logger.info("Orchestrator: Starting NEST simulation process.")
        nest_script = Path(__file__).parent / "../Nest/run_mpi_nest.sh"
        argv=[
            '/bin/sh',
            str(nest_script.resolve()),
            mpirun,
            str(param_co_simulation['nb_MPI_nest']),
            str(1),
            str(results_path),
        ]
        logger.info(f"Orchestrator: NEST launch command: {' '.join(argv)}")
        processes.append(subprocess.Popen(argv,
                 # need to check if it's needed or not (doesn't work for me)
                 stdin=None,stdout=None,stderr=None,close_fds=True, #close the link with parent process
                 ))
        # Wait for spike generator and detector files using pathlib
        spike_gen_unlock = results_path / 'nest' / 'spike_generator.txt.unlock'
        while not spike_gen_unlock.exists():
            logger.info("spike generator ids not found yet, retry in 1 second")
            time.sleep(1)
        spike_gen_unlock.unlink()
        spike_generator = np.loadtxt(str(results_path / 'nest' / 'spike_generator.txt'), dtype=int)
        
        spike_det_unlock = results_path / 'nest' / 'spike_detector.txt.unlock'
        while not spike_det_unlock.exists():
            logger.info("spike detector ids not found yet, retry in 1 second")
            time.sleep(1)
        spike_det_unlock.unlink()
        spike_detector = np.loadtxt(str(results_path / 'nest' / 'spike_detector.txt'), dtype=int)
        # case of one spike detector
        try :
            spike_detector = np.array([int(spike_detector)])
            spike_generator = np.expand_dims(spike_generator,0)
        except:
            pass

        # print ids of nest population
        print("Ids of different populations of Nest :\n")
        population_file = results_path / 'nest' / 'population_GIDs.dat'
        try:
            with population_file.open('r', encoding='utf-8') as f:
                print(f.read())
        except (IOError, OSError) as e:
            logger.warning(f"Could not read population GIDs file {population_file}: {e}")
            print("Population GIDs file not available")

        # Run TVB in co-simulation
        logger.info("Orchestrator: Starting TVB simulation process.")
        tvb_script = Path(__file__).parent / "../Tvb/run_mpi_tvb.sh"
        argv = [
            '/bin/sh',
            str(tvb_script.resolve()),
            mpirun,
            str(1),
            str(results_path),
        ]
        logger.info(f"Orchestrator: TVB launch command: {' '.join(argv)}")
        processes.append(subprocess.Popen(argv,
                         # need to check if it's needed or not (doesn't work for me)
                         stdin=None, stdout=None, stderr=None, close_fds=True,  # close the link with parent process
                         ))
        # wait until TVB is ready
        for id_proxy_single in id_proxy:
            while not os.path.exists(results_path+'/translation/receive_from_tvb/'+str(id_proxy_single)+'.txt.unlock'):
                logger.info(f"TVB proxy {id_proxy_single} not found yet, retry in 1 second")
                time.sleep(1)
            os.remove(results_path+'/translation/receive_from_tvb/'+str(id_proxy_single)+'.txt.unlock')
        logger.info("TVB is ready to use")

        # create translator between Nest to TVB :
        # one by proxy/spikedetector
        for index,id_spike_detector in enumerate(spike_detector):
            logger.info(f"Orchestrator: Starting nest_to_tvb translator for spike_detector: {id_spike_detector} and proxy: {id_proxy[index]}")
            dir_path = os.path.dirname(os.path.realpath(__file__))+"/../translation/run_mpi_nest_to_tvb.sh"
            argv=[ '/bin/sh',
                   dir_path,
                   mpirun,
                   results_path,
                   "/translation/spike_detector/"+str(id_spike_detector)+".txt",
                   "/translation/send_to_tvb/"+str(id_proxy[index])+".txt",
                   ]
            logger.info(f"Orchestrator: nest_to_tvb translator launch command: {' '.join(argv)}")
            processes.append(subprocess.Popen(argv,
                             #need to check if it's needed or not (doesn't work for me)
                             stdin=None,stdout=None,stderr=None,close_fds=True, #close the link with parent process
                             ))

        # create translator between TVB to Nest:
        # one by proxy/id_region
        for index,ids_spike_generator in enumerate(spike_generator):
            logger.info(f"Orchestrator: Starting tvb_to_nest translator for spike_generator: {ids_spike_generator[0]} and proxy: {id_proxy[index]}")
            dir_path = os.path.dirname(os.path.realpath(__file__))+"/../translation/run_mpi_tvb_to_nest.sh"
            argv=[ '/bin/sh',
                   dir_path,
                   mpirun,
                   results_path+"/translation/spike_generator/",
                   str(ids_spike_generator[0]),
                   str(len(ids_spike_generator)),
                   "/../receive_from_tvb/"+str(id_proxy[index])+".txt",
                   ]
            logger.info(f"Orchestrator: tvb_to_nest translator launch command: {' '.join(argv)}")
            processes.append(subprocess.Popen(argv,
                             #need to check if it's needed or not (doesn't work for me)
                             stdin=None,stdout=None,stderr=None,close_fds=True, #close the link with parent process
                             ))
    else:
        if param_co_simulation['nb_MPI_nest'] != 0:
            # Second case : Only nest simulation
            if param_co_simulation['record_MPI']:
                # translator for saving some result
                translation_dir = results_path / 'translation'
                translation_dir.mkdir(exist_ok=True)
                end = parameters['end']

                #initialise Nest before the communication
                dir_path = os.path.dirname(os.path.realpath(__file__))+"/../Nest/run_mpi_nest.sh"
                argv=[
                    '/bin/sh',
                    dir_path,
                    mpirun,
                    str(param_co_simulation['nb_MPI_nest']),
                    str(1),
                    results_path,
                ]
                processes.append(subprocess.Popen(argv,
                         # need to check if it's needed or not (doesn't work for me)
                         stdin=None,stdout=None,stderr=None,close_fds=True, #close the link with parent process
                         ))
                while not os.path.exists(results_path+'/nest/spike_detector.txt.unlock'):
                    logger.info("spike detector ids not found yet, retry in 1 second")
                    time.sleep(1)
                os.remove(results_path+'/nest/spike_detector.txt.unlock')
                spike_detector = np.loadtxt(results_path+'/nest/spike_detector.txt',dtype=int)

                # Create folder for the translation part
                spike_detector_dir = results_path / 'translation' / 'spike_detector'
                save_dir = results_path / 'translation' / 'save'
                spike_detector_dir.mkdir(parents=True, exist_ok=True)
                save_dir.mkdir(parents=True, exist_ok=True)

                for id_spike_detector in spike_detector:
                    dir_path = os.path.dirname(os.path.realpath(__file__))+"/../translation/run_mpi_nest_save.sh"
                    argv=[ '/bin/sh',
                           dir_path,
                           mpirun,
                           results_path,
                           "/translation/spike_detector/"+str(id_spike_detector)+".txt",
                           results_path+"/translation/save/"+str(id_spike_detector),
                           str(end)
                           ]
                    processes.append(subprocess.Popen(argv,
                                 #need to check if it's needed or not (doesn't work for me)
                                 stdin=None,stdout=None,stderr=None,close_fds=True, #close the link with parent process
                                 ))
            else:
                #Run Nest with MPI
                dir_path = os.path.dirname(os.path.realpath(__file__))+"/../Nest/run_mpi_nest.sh"
                argv=[
                    '/bin/sh',
                    dir_path,
                    mpirun,
                    str(param_co_simulation['nb_MPI_nest']),
                    str(0),
                    results_path,
                ]
                processes.append(subprocess.Popen(argv,
                         # need to check if it's needed or not (doesn't work for me)
                         stdin=None,stdout=None,stderr=None,close_fds=True, #close the link with parent process
                         ))
        else:
            # TODO change the API for include Nest without MPI
            # Run TVB in co-simulation
            dir_path = os.path.dirname(os.path.realpath(__file__)) + "/../Tvb/simulation_Zerlaut.py"
            argv = [
                'python3',
                dir_path,
                str(0),
                results_path,
            ]
            processes.append(subprocess.Popen(argv,
                             # need to check if it's needed or not (doesn't work for me)
                             stdin=None, stdout=None, stderr=None, close_fds=True,  # close the link with parent process
                             ))
    # FAT END POINT : add monitoring of the different process
    for process in processes:
        process.wait()
    logger.info('time: '+str(datetime.datetime.now())+' END SIMULATION \n')

def run_exploration(results_path,parameter_default,dict_variable,begin,end):
    """
    Run one simulation of the exploration
    :param results_path: the folder where to save spikes
    :param parameter_default: parameters by default of the exploration
    :param dict_variable : dictionary with the variable change
    :param begin:  when start the recording simulation ( not take in count for tvb (start always to zeros )
    :param end: when end the recording simulation and the simulation
    :return: nothing
    """
    # Create the folder for results using pathlib
    results_dir = Path.cwd() / results_path
    results_dir.mkdir(parents=True, exist_ok=True)
    
    # Remove synchronization file if it exists
    sync_file = results_dir / 'parameter.py'
    try:
        sync_file.unlink(missing_ok=True)  # use it for synchronise all mpi the beginning
    except OSError:
        pass
        
    # generate and save parameter for the simulation
    parameters = generate_parameter(parameter_default, results_path, dict_variable)
    save_parameter(parameters, results_path, begin, end)
    
    # check if the parameter file is available using pathlib
    param_file = results_dir / 'parameter.json'
    while not param_file.exists():
        time.sleep(1)
    run(str(param_file))


def run_exploration_2D(path,parameter_default,dict_variables,begin,end):
    """
    Run exploration of parameter in 2 dimensions
    :param path: for the result of the simulations
    :param parameter_default: the parameters by defaults of the simulations
    :param dict_variables: the variables and there range of value for the simulations
    :param begin: when start the recording simulation ( not take in count for tvb (start always to zeros )
    :param end: when end the recording simulation and the simulation
    :return:
    """
    name_variable_1,name_variable_2 = dict_variables.keys()
    print(path)
    for variable_1 in  dict_variables[name_variable_1]:
        for variable_2 in  dict_variables[name_variable_2]:
            # try:
            print('SIMULATION : '+name_variable_1+': '+str(variable_1)+' '+name_variable_2+': '+str(variable_2))
            results_path=path+'_'+name_variable_1+'_'+str(variable_1)+'_'+name_variable_2+'_'+str(variable_2)
            run_exploration(results_path,parameter_default,{name_variable_1:variable_1,name_variable_2:variable_2},begin,end)
            # except:
            #     sys.stderr.write('time: '+str(datetime.datetime.now())+' error: ERROR in simulation \n')


# =================== Builder Pattern Integration ===================
# Enhanced experiment configuration using the Builder pattern

def run_experiment_builder(experiment) -> None:
    """
    Run an experiment configured using the ExperimentBuilder pattern.
    
    This function provides an enhanced interface for running experiments
    with better parameter validation, metadata tracking, and result organization.
    
    Args:
        experiment: Experiment object created by ExperimentBuilder
        
    Example:
        # Create experiment using Builder pattern
        experiment = (ExperimentBuilder()
                     .with_base_parameters(parameter_module)
                     .with_results_path("./my_experiment/")
                     .explore_parameter("g", [1.0, 1.5, 2.0])
                     .with_experiment_name("G parameter exploration")
                     .build())
        
        # Run the experiment
        run_experiment_builder(experiment)
    """
    if not BUILDER_AVAILABLE:
        raise ImportError("Builder pattern not available. Install Pydantic for enhanced experiment features.")
    
    logging.info(f"Running experiment: {experiment.experiment_name or 'Unnamed experiment'}")
    
    # Save experiment metadata
    experiment.save_experiment_metadata()
    
    # Get experiment info for logging
    experiment_info = experiment.get_experiment_info()
    logging.info(f"Total parameter combinations: {experiment_info['num_parameter_combinations']}")
    logging.info(f"Results path: {experiment_info['results_path']}")
    
    # Generate all parameter sets
    parameter_sets = experiment.generate_parameter_sets()
    
    # Run simulation for each parameter set
    for i, parameter_set in enumerate(parameter_sets):
        logging.info(f"Running simulation {i+1}/{len(parameter_sets)}")
        
        # Create unique results path for this parameter combination
        if len(parameter_sets) > 1:
            results_path = Path(experiment.results_path) / f"run_{i+1:03d}"
        else:
            results_path = Path(experiment.results_path)
            
        results_path.mkdir(parents=True, exist_ok=True)
        
        # Update parameter set with specific results path
        if hasattr(parameter_set, 'model_dump'):
            # Pydantic model - need to update through reconstruction
            param_dict = parameter_set.model_dump()
            param_dict['result_path'] = str(results_path) + "/"
            # Reconstruct parameter set with new path
            from nest_elephant_tvb.orchestrator.validation.validators import ParameterValidator
            parameter_set = ParameterValidator.validate_dict(param_dict)
        else:
            # Dictionary - direct update
            parameter_set['result_path'] = str(results_path) + "/"
        
        # Save parameters for this run
        from nest_elephant_tvb.orchestrator.parameters_manager import save_parameter
        
        # Get timing parameters with robust error handling
        # Priority: ExperimentBuilder settings > parameter_set values > defaults
        if experiment.simulation_begin is not None:
            begin = experiment.simulation_begin
        else:
            try:
                begin = BackwardCompatibilityManager.get_parameter_value(parameter_set, 'begin')
            except (AttributeError, KeyError, TypeError):
                begin = 0.0
            
        if experiment.simulation_end is not None:
            end = experiment.simulation_end
        else:
            try:
                end = BackwardCompatibilityManager.get_parameter_value(parameter_set, 'end')
            except (AttributeError, KeyError, TypeError):
                end = 100.0
        
        save_parameter(parameter_set, str(results_path), begin, end)
        
        # Run the actual simulation
        _run_simulation_with_parameters(parameter_set, str(results_path))
    
    logging.info("Experiment completed successfully!")
    logging.info(f"Results saved to: {experiment.results_path}")


def run_exploration_builder(parameter_module, results_path: str, 
                           exploration_dict: dict, experiment_name: str = None) -> None:
    """
    Enhanced parameter exploration using Builder pattern.
    
    This is a convenience function that combines the Builder pattern with
    the traditional parameter exploration workflow.
    
    Args:
        parameter_module: Base parameter module object
        results_path: Output directory path
        exploration_dict: Dictionary of parameters to explore
        experiment_name: Optional experiment name
        
    Example:
        run_exploration_builder(
            parameter_module=test_nest,
            results_path="./my_exploration/",
            exploration_dict={"g": [1.0, 1.5, 2.0], "mean_I_ext": [0.0, 0.1]},
            experiment_name="Parameter sensitivity analysis"
        )
    """
    if not BUILDER_AVAILABLE:
        logging.warning("Builder pattern not available, falling back to legacy exploration")
        # Fallback to traditional exploration
        for param_name, values in exploration_dict.items():
            for value in values:
                run_exploration(results_path, parameter_module, {param_name: value}, 0.0, 100.0)
        return
    
    # Create experiment using Builder pattern
    builder = ExperimentBuilder()
    experiment = (builder
                  .with_base_parameters(parameter_module)
                  .with_results_path(results_path)
                  .explore_parameters(exploration_dict)
                  .with_experiment_name(experiment_name)
                  .with_validation(enabled=True)
                  .build())
    
    # Run the experiment
    run_experiment_builder(experiment)


def _run_simulation_with_parameters(parameter_set, results_path: str) -> None:
    """
    Internal function to run simulation with given parameter set.
    
    This extracts the simulation logic from the run() function to enable
    reuse by the Builder pattern functions.
    
    Args:
        parameter_set: Parameter configuration (dict or Pydantic model)
        results_path: Results output directory
    """
    # This would contain the actual simulation execution logic
    # For now, we'll create a simplified version that calls the existing run logic
    
    # Create temporary parameter file
    temp_param_file = Path(results_path) / "temp_parameters.json"
    
    # Convert parameter set to dict for JSON serialization
    if hasattr(parameter_set, 'model_dump'):
        param_dict = parameter_set.model_dump()
    else:
        param_dict = parameter_set
    
    # Save temporary parameter file
    import json
    with temp_param_file.open('w', encoding='utf-8') as f:
        json.dump(param_dict, f, indent=2, ensure_ascii=False)
    
    try:
        # Use existing run function with temporary parameter file
        run(str(temp_param_file))
    finally:
        # Clean up temporary file
        if temp_param_file.exists():
            temp_param_file.unlink()


if __name__ == "__main__":
    if len(sys.argv)==2:
        run(parameters_file=sys.argv[1])
    else:
        print('missing argument')
