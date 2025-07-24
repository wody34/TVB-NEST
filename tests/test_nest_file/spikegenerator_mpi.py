#  Copyright 2020 Forschungszentrum Jülich GmbH and Aix-Marseille Université
# "Licensed to the Apache Software Foundation (ASF) under one or more contributor license agreements; and to You under the Apache License, Version 2.0. "

'''
spike generator with mpi backend
'''

import nest
import numpy
import os
from mpi4py import MPI
import pandas as pd

def process_spikes_to_dataframe(all_spikes):
    """Processes spike data from a gathered list into a sorted pandas DataFrame."""
    spikes_list = []
    # Filter out possible None entries from ranks with no data
    for rank_data in filter(None, all_spikes):
        if 'senders' in rank_data and 'times' in rank_data and rank_data['senders'].size > 0:
            for sender, time in zip(rank_data['senders'], rank_data['times']):
                spikes_list.append({'sender_gid': sender, 'time_ms': time})

    if not spikes_list:
        return pd.DataFrame(columns=['sender_gid', 'time_ms'])

    df = pd.DataFrame(spikes_list)
    df = df.sort_values(by='time_ms').reset_index(drop=True)
    return df

nest.ResetKernel()
# get rank of the MPI process
rank = nest.Rank()
# Set parameter of kernel. The most important is the set of the path
nest.SetKernelStatus({"overwrite_files": True,
                      "data_path": os.path.dirname(os.path.realpath(__file__))+"/../",
                      })
# Creation of neurons
n = nest.Create("iaf_psc_alpha",
                params={"tau_syn_ex": 1.0, "V_reset": -70.0})
n_2 = nest.Create("iaf_psc_alpha",
                params={"tau_syn_ex": 2.0, "V_reset": -70.0})
# creation of spike detector with MPI or not
m = nest.Create("spike_recorder",
                params={
                        "record_to": "mpi",
                        "label": "test_nest_spike"})
m_2 = nest.Create("spike_recorder",
                params={
                    "record_to": "mpi",
                    "label":"test_nest_spike"})
m_3 = nest.Create("spike_recorder",
                  params={
                      "record_to": "memory",
                      "label":"test_nest_spike"})
m_4 = nest.Create("spike_recorder",
                  params={
                      "record_to": "memory",
                      "label":"test_nest_spike"})
# Creation of spike generator with MPI or not
s_ex = nest.Create("spike_generator",
                   params={"spike_times": numpy.array([]),
                           'stimulus_source':'mpi',
                           "label":"test_nest_spike"})
s_in = nest.Create("spike_generator",
                   params={"spike_times": numpy.array([15.0, 25.0, 55.0])})
# Creation of current generator
dc = nest.Create("dc_generator",
                 params={"amplitude":900.0})
dc_2 = nest.Create("dc_generator",
                 params={"amplitude":1000.0})
print("create nodes")
# Creation of connections
nest.Connect(s_ex, n, syn_spec={"weight": 1000.0})
nest.Connect(s_in, n_2, syn_spec={"weight": 1000.0})
nest.Connect(n,m)
nest.Connect(n_2,m)
nest.Connect(s_ex,m_2)
nest.Connect(s_in,m_2)
nest.Connect(n,m_3)
nest.Connect(n_2,m_3)
nest.Connect(s_ex,m_4)
nest.Connect(s_in,m_4)
print("create connect")

# --- GID 확인을 위한 출력 추가 ---
if rank == 0:
    print("---------------- GID 확인 -----------------")
    print(f"고정 입력 생성기 (s_in): {s_in}")
    print(f"MPI 입력 생성기 (s_ex): {s_ex}")
    print(f"뉴런 (n): {n}")
    print(f"뉴런 (n_2): {n_2}")
    print(f"MPI 기록기 1 (m): {m}")
    print(f"MPI 기록기 2 (m_2): {m_2}")
    print(f"메모리 기록기 1 (m_3): {m_3}")
    print(f"메모리 기록기 2 (m_4): {m_4}")
    print("-------------------------------------------")

'''
A network simulation with a duration of 5*100 ms is started.
'''
print("Spike generator 1 {} and 2 {}".format(s_in, s_ex))
nest.Prepare()
print("Start run")
nest.Run(200.)
nest.Run(200.)
nest.Run(200.)
nest.Run(200.)

# # Save spike data to file
# spikes_m3_local = nest.GetStatus(m_3)[0]['events']
# spikes_m4_local = nest.GetStatus(m_4)[0]['events']

nest.Cleanup()

# comm = MPI.COMM_WORLD
# # Gather spike data from all ranks to rank 0
# all_spikes_m3 = comm.gather(spikes_m3_local, root=0)
# all_spikes_m4 = comm.gather(spikes_m4_local, root=0)

# # Rank 0 processes and saves the data
# if rank == 0:
#     # --- Process spikes using pandas ---
#     m3_df = process_spikes_to_dataframe(all_spikes_m3)
#     m4_df = process_spikes_to_dataframe(all_spikes_m4)

#     # --- Save to CSV in the designated folder ---
#     output_dir = "test_nest_spike"
#     os.makedirs(output_dir, exist_ok=True)

#     m3_df.to_csv(os.path.join(output_dir, 'm3_spikes_from_memory.csv'), index=False)
#     m4_df.to_csv(os.path.join(output_dir, 'm4_spikes_from_memory.csv'), index=False)

#     print(f"\nSUCCESS: Saved in-memory recorder data to {output_dir}/")
