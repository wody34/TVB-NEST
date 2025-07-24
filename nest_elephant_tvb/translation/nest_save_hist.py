#  Copyright 2020 Forschungszentrum Jülich GmbH and Aix-Marseille Université
# "Licensed to the Apache Software Foundation (ASF) under one or more contributor license agreements; and to You under the Apache License, Version 2.0. "

import numpy as np
import json
from mpi4py import MPI
from threading import Thread, Lock
import pathlib
import time
from nest_elephant_tvb.translation.science_nest_to_tvb import store_data
from nest_elephant_tvb.translation.nest_to_tvb import create_logger

def receive(logger, store, status_data, buffer, comm_receiver, lock_status):
    """
    Receive data from the Nest simulation and put it in the shared buffer.
    """
    status = MPI.Status()
    count = 0 # step counter
    
    while True:
        check = np.empty(1, dtype='b')
        # Probing first to get tag and source without consuming the message
        try:
            if comm_receiver.Iprobe(source=MPI.ANY_SOURCE, tag=MPI.ANY_TAG, status=status) == False:
                time.sleep(0.001)
                continue
        except MPI.Exception:
            logger.info("Receive: MPI Exception, probably disconnected. Exiting.")
            break
            
        tag = status.Get_tag()
        source = status.Get_source()
        
        # Now, receive the message
        comm_receiver.Recv([check, 1, MPI.CXX_BOOL], source=source, tag=tag, status=status)

        if tag == 0: # data is coming
            # send confirmation
            comm_receiver.Send([np.array(True, dtype='b'), MPI.BOOL], dest=source, tag=0)
            # receive shape
            shape = np.empty(1, dtype='i')
            comm_receiver.Recv([shape, 1, MPI.INT], source=source, tag=0, status=status)
            # receive data
            data = np.empty(shape[0], dtype='d')
            comm_receiver.Recv([data, MPI.DOUBLE], source=source, tag=0, status=status)
            
            while status_data[0] != 1:
                time.sleep(0.001)
            
            with lock_status:
                status_data[0] = 0 # busy
            
            store.add_spikes(count, data)
            buffer[0] = store.return_data()
            
            with lock_status:
                status_data[0] = 2 # ready
                
        elif tag == 1: # end of step
            logger.info(f"Receive: End of step {count}")
            count += 1
            
        elif tag == 2: # end of simulation
            logger.info("Receive: End of simulation signal received.")
            with lock_status:
                status_data[0] = 3 # signal to stop `save` thread
            break
        else:
            logger.error(f"Receive: Unknown tag {tag}")
    
    logger.info("Receive thread finished.")


def save(path,logger,nb_step,step_save,status_data,buffer, lock_status):
    '''
    WARNING never ending
    :param path:  folder which will contain the configuration file
    :param logger : the logger fro the thread
    :param nb_step : number of time for saving data
    :param step_save : number of integration step to save in same time
    :param status_data: the status of the buffer (SHARED between thread)
    :param buffer: the buffer which contains the data (SHARED between thread)
    :return:
    '''
    # initialisation variable
    buffer_save = None
    count=0
    while count<nb_step: # FAT END POINT
        logger.info("Nest save : save "+str(count))
        # send the rate when there ready
        while status_data[0] == 1:
            time.sleep(0.1)
            if status_data[0] == 3: # End signal from receive
                break
            pass
        if status_data[0] == 3: # End signal from receive
            logger.info('Save : get ending signal')
            break
        if buffer_save is None:
            logger.info("buffer initialise buffer : "+str(count))
            buffer_save = buffer[0]
        elif count % step_save == 0:
            logger.info("buffer save buffer : "+str(count))
            buffer_save = np.concatenate((buffer_save,buffer[0]))
            np.save(path+"_"+str(count)+".npy",buffer_save)
            buffer_save = None
        else:
            logger.info("fill the buffer : "+str(count))
            buffer_save = np.concatenate((buffer_save,buffer[0]))
        with lock_status:
            status_data[0]=1
        count+=1
    logger.info('Save : ending');sys.stdout.flush()
    if buffer_save is not None:
        np.save(path + "_" + str(count) + ".npy", buffer_save)
    return


if __name__ == "__main__":
    import sys
    if len(sys.argv)==5:
        path_folder_config = sys.argv[1]
        file_spike_detector = sys.argv[2]
        path_folder_save = sys.argv[3]
        end = float(sys.argv[4])

        # parameters for the module
        # take the parameters and instantiate objects for analysing data
        with open(path_folder_config+'/parameter.json') as f:
            parameters = json.load(f)
        param = parameters['param_record_MPI']
        time_synch = param['synch']
        nb_step = np.ceil(end/time_synch)
        step_save = param['save_step']
        level_log = param['level_log']
        logger_master = create_logger(path_folder_config, 'nest_to_tvb_master', level_log)

        # variable for communication between thread
        status_data=[1] # status of the buffer
        buffer=[np.array([])]
        lock_status = Lock()

        # object for analysing data
        store=store_data(path_folder_config,param)

        ############
        # Open the MPI port connection for receiver
        info = MPI.INFO_NULL
        root=0

        logger_master.info('Translate Receive: before open_port')
        port_receive = MPI.Open_port(info)
        logger_master.info('Translate Receive: after open_port')
        # Write file configuration of the port
        path_to_files = path_folder_config + file_spike_detector
        fport = open(path_to_files, "w+")
        fport.write(port_receive)
        fport.close()
        # rename forces that when the file is there it also contains the port
        pathlib.Path(path_to_files+'.unlock').touch()
        logger_master.info('Translate Receive: path_file: ' + path_to_files)
        # Wait until connection
        logger_master.info('Waiting communication')
        comm_receiver = MPI.COMM_WORLD.Accept(port_receive, info, root)
        logger_master.info('get communication and start thread')
        #########################

        # create the thread for receive and save data
        logger_receive = create_logger(path_folder_config, 'nest_to_tvb_receive', level_log)
        logger_save = create_logger(path_folder_config, 'nest_to_tvb_send', level_log)
        th_receive = Thread(target=receive,
                            args=(logger_receive, store, status_data, buffer, comm_receiver, lock_status))
        th_save = Thread(target=save, args=(path_folder_save,logger_save,nb_step,step_save,status_data,buffer, lock_status))

        # start the threads
        # FAT END POINT
        logger_master.info('start thread')
        th_receive.start()
        th_save.start()
        th_receive.join()
        th_save.join()
        logger_master.info('join thread')
        MPI.Close_port(port_receive)
        MPI.Finalize()
    else:
        print('missing argument')