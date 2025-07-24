#  Copyright 2020 Forschungszentrum Jülich GmbH and Aix-Marseille Université
# "Licensed to the Apache Software Foundation (ASF) under one or more contributor license agreements; and to You under the Apache License, Version 2.0. "

import numpy as np
import os
from mpi4py import MPI
import pandas as pd
import sys
from pathlib import Path

def analyse(path,nb_mpi):
    """
    simulate the recorder module
    :param path: the file for the configurations of the connection
    :param nb_mpi: number of mpi rank for testing multi-threading and MPI simulation
    :return:
    """
    #Start communication channels
    path_to_files = path
    #For NEST
    # Init connection
    print("Waiting for port details")
    info = MPI.INFO_NULL
    root=0
    port = MPI.Open_port(info)
    path_to_files = Path(path_to_files)
    gid = path_to_files.stem
    path_to_files.write_text(port)
    print(f'wait connection {port} in {gid}', flush=True)
    comm = MPI.COMM_WORLD.Accept(port, info, root)
    print(f'connect to {port} in {gid}', flush=True)

    # list for storing all data
    received_spikes = []
    #test one rate
    status_ = MPI.Status()
    check = np.empty(1,dtype='b')
    source_sending = np.arange(0,comm.Get_remote_size(),1) # list of all the process for the commmunication
    while(True):
        comm.Recv([check, 1, MPI.CXX_BOOL], source=MPI.ANY_SOURCE, tag=MPI.ANY_TAG, status=status_)
        print(f" start to send in {gid}" if gid=="4" else "", flush=True)
        print(f" status a tag {status_.Get_tag()} source {status_.Get_source()}" if gid=="4" else "", flush=True)
        if status_.Get_tag() == 0:
            for i in range(nb_mpi-1):
                comm.Recv([check, 1, MPI.CXX_BOOL], source=MPI.ANY_SOURCE, tag=0, status=status_)
            for source in source_sending:
                print(f"source is {source} in {gid}" if gid=="4" else "", flush=True)
                comm.Send([np.array(True,dtype='b'),MPI.BOOL],dest=source,tag=0)
                shape = np.empty(1, dtype='i')
                comm.Recv([shape, 1, MPI.INT], source=source, tag=0, status=status_)
                print(f"shape is {shape[0]} in {gid}" if gid=="4" else "", flush=True)
                data = np.empty(shape[0], dtype='d')
                comm.Recv([data, shape[0], MPI.DOUBLE], source=status_.Get_source(), tag=0, status=status_)
                
                # We expect data in triplets (recorder_gid, sender_gid, time_ms).
                # Only process arrays where the size is a multiple of 3.
                if data.size > 0 and data.size % 3 == 0:
                    received_spikes.extend(data.reshape(-1, 3).tolist())
                elif data.size > 0:
                    # Log unexpected data sizes for debugging, but don't try to process them.
                    print(f"Warning: Received data of unexpected size {data.size} from source {source}. Content: {data}. Skipping.", file=sys.stderr)
                
                print(f"source: {source} data received: {data.size} elements" if gid=="4" else "", flush=True)
        elif status_.Get_tag() == 1:
            print("end run", flush=True)
        elif status_.Get_tag() ==2:
            for i in range(nb_mpi-1):
                print(" receive ending", flush=True)
                comm.Recv([check, 1, MPI.CXX_BOOL], source=MPI.ANY_SOURCE, tag=MPI.ANY_TAG, status=status_)
            print("end simulation", flush=True)
            break
        else:
            print(status_.Get_tag())
            break
    comm.Disconnect()
    MPI.Close_port(port)

    # After loop, process and save all received spikes using pandas
    if received_spikes:
        print(f"Total spikes received: {len(received_spikes)}")
        print(f"--- RECORDER {path} AGGREGATING AND SAVING RESULTS ---")

        # Convert to a pandas DataFrame for easier processing
        
        df = pd.DataFrame(received_spikes, columns=['recorder_gid', 'sender_gid', 'time_ms'])

        # Ensure data types are correct
        df['recorder_gid'] = df['recorder_gid'].astype(int)
        df['sender_gid'] = df['sender_gid'].astype(int)
        df['time_ms'] = df['time_ms'].astype(float)
        
        # Sort by time_ms
        df = df.sort_values(by='time_ms')
        
        # Save spikes for each sender
        # Ensure the base path is a directory
        output_dir = Path(path).parent
        output_dir.mkdir(parents=True, exist_ok=True)
        output_filename = output_dir / f"spikes_from_recorder_{gid}.csv"
        df.to_csv(output_filename, index=False, float_format='%g')
        print(f"Saved {len(df)} spikes from recorder {gid} to {output_filename}")
        print("-" * 60)

    os.remove(path_to_files)
    print('exit')
    MPI.Finalize()

if __name__ == "__main__":
    if len(sys.argv)== 3 :
        analyse(sys.argv[1],int(sys.argv[2]))
    else:
        print('missing argument')

