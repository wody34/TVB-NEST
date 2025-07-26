#!/usr/bin/env python3
"""
Python Test Coordinator - Alternative to Shell Script Orchestration

이 모듈은 tests/ 디렉토리의 복잡한 shell script 조정을 대체하는 Python 기반 솔루션입니다.
.sh 파일의 필요성을 제거하면서 더 나은 에러 처리, 로깅, 크로스 플랫폼 호환성을 제공합니다.
"""

import os
import sys
import subprocess
import tempfile
import shutil
import time
import threading
import multiprocessing
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from contextlib import contextmanager

@dataclass
class MPIProcess:
    """MPI 프로세스 설정"""
    script_path: str
    args: List[str]
    num_processes: int = 1
    background: bool = True
    communication_file: Optional[str] = None
    timeout: Optional[int] = None

@dataclass
class TestConfiguration:
    """테스트 설정 매개변수"""
    name: str
    temp_dir: str
    processes: List[MPIProcess]
    setup_files: List[str] = None
    cleanup_dirs: List[str] = None
    wait_for_all: bool = True

class PythonTestCoordinator:
    """Shell script를 대체하는 Python 기반 테스트 코디네이터"""
    
    def __init__(self, base_dir: str = None):
        self.base_dir = Path(base_dir) if base_dir else Path.cwd()
        self.temp_dirs = []
        self.running_processes = []
        self.logger = self._setup_logging()
        
        # init.sh와 동등한 환경 초기화
        self._setup_environment()
    
    def _setup_logging(self) -> logging.Logger:
        """로깅 설정"""
        logger = logging.getLogger('test_coordinator')
        logger.setLevel(logging.INFO)
        
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        return logger
    
    def _setup_environment(self):
        """init.sh와 동등한 환경 변수 설정"""
        package_path = str(self.base_dir)
        python_lib = str(self.base_dir / "venv" / "lib" / "python3.9" / "site-packages")
        nest_lib = str(self.base_dir / "lib" / "nest_run" / "lib" / "python3.9" / "site-packages")
        
        current_pythonpath = os.environ.get('PYTHONPATH', '')
        new_paths = [package_path, python_lib, nest_lib]
        
        if current_pythonpath:
            os.environ['PYTHONPATH'] = ':'.join(new_paths + [current_pythonpath])
        else:
            os.environ['PYTHONPATH'] = ':'.join(new_paths)
        
        # MPI 실행 명령 설정
        self.mpi_cmd = os.environ.get('RUN', 'mpirun')
        
        self.logger.info(f"환경 설정 완료. PYTHONPATH: {os.environ['PYTHONPATH']}")
        self.logger.info(f"MPI 명령: {self.mpi_cmd}")
    
    @contextmanager
    def temporary_directory(self, prefix: str = "test_"):
        """임시 디렉토리 생성/정리를 위한 컨텍스트 매니저"""
        temp_dir = tempfile.mkdtemp(prefix=prefix)
        self.temp_dirs.append(temp_dir)
        try:
            yield temp_dir
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                if temp_dir in self.temp_dirs:
                    self.temp_dirs.remove(temp_dir)
    
    def run_mpi_process(self, process_config: MPIProcess, temp_dir: str) -> subprocess.Popen:
        """단일 MPI 프로세스 실행"""
        cmd = [
            self.mpi_cmd,
            '-n', str(process_config.num_processes),
            'python3',
            str(self.base_dir / process_config.script_path)
        ] + process_config.args
        
        # 통신 파일 경로 추가 (지정된 경우)
        if process_config.communication_file:
            comm_file_path = os.path.join(temp_dir, process_config.communication_file)
            cmd.append(comm_file_path)
        
        self.logger.info(f"MPI 프로세스 시작: {' '.join(cmd)}")
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if process_config.background:
            self.running_processes.append(process)
        
        return process
    
    def wait_for_processes(self, processes: List[subprocess.Popen], timeout: int = 300):
        """여러 프로세스 완료 대기"""
        for i, process in enumerate(processes):
            try:
                stdout, stderr = process.communicate(timeout=timeout)
                if process.returncode != 0:
                    self.logger.error(f"프로세스 {i} 실패 (return code {process.returncode})")
                    self.logger.error(f"STDERR: {stderr}")
                else:
                    self.logger.info(f"프로세스 {i} 성공적으로 완료")
                    if stdout:
                        self.logger.debug(f"STDOUT: {stdout}")
            except subprocess.TimeoutExpired:
                self.logger.error(f"프로세스 {i} 타임아웃 ({timeout}초)")
                process.kill()
    
    def run_test_configuration(self, config: TestConfiguration):
        """완전한 테스트 설정 실행"""
        self.logger.info(f"테스트 시작: {config.name}")
        
        with self.temporary_directory(f"{config.name}_") as temp_dir:
            processes = []
            
            # 필요한 경우 설정 파일 복사
            if config.setup_files:
                for setup_file in config.setup_files:
                    src = self.base_dir / setup_file
                    dst = Path(temp_dir) / Path(setup_file).name
                    if src.exists():
                        shutil.copy2(src, dst)
            
            # 백그라운드 프로세스 먼저 시작
            background_processes = [p for p in config.processes if p.background]
            for process_config in background_processes:
                process = self.run_mpi_process(process_config, temp_dir)
                processes.append(process)
                time.sleep(0.5)  # 포트 파일 생성 보장을 위한 짧은 지연
            
            # 포그라운드 프로세스 시작
            foreground_processes = [p for p in config.processes if not p.background]
            for process_config in foreground_processes:
                process = self.run_mpi_process(process_config, temp_dir)
                processes.append(process)
            
            # 완료 대기
            if config.wait_for_all:
                self.wait_for_processes(processes)
            
            self.logger.info(f"테스트 완료: {config.name}")
    
    def cleanup(self):
        """실행 중인 모든 프로세스와 임시 디렉토리 정리"""
        for process in self.running_processes:
            if process.poll() is None:  # 프로세스가 아직 실행 중
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
        
        for temp_dir in self.temp_dirs:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
    
    # Shell script를 대체하는 특정 테스트 메서드들
    
    def test_input_nest_spike(self):
        """test_input_nest_spike.sh 대체"""
        config = TestConfiguration(
            name="input_nest_spike",
            temp_dir="test_nest_spike",
            processes=[
                MPIProcess(
                    script_path="nest_elephant_tvb/translation/test_file/spike_nest_input/input_region_activity.py",
                    args=[],
                    communication_file="7.txt",
                    background=True
                ),
                MPIProcess(
                    script_path="nest_elephant_tvb/translation/test_file/record_nest_activity/record_region_activity.py",
                    args=[],
                    communication_file="3.txt",
                    background=True
                ),
                MPIProcess(
                    script_path="nest_elephant_tvb/translation/test_file/record_nest_activity/record_region_activity.py",
                    args=[],
                    communication_file="4.txt",
                    background=True
                ),
                MPIProcess(
                    script_path="tests/test_nest_file/spikegenerator_mpi.py",
                    args=[],
                    background=False
                )
            ]
        )
        self.run_test_configuration(config)
    
    def test_input_nest_current(self):
        """test_input_nest_current.sh 대체"""
        config = TestConfiguration(
            name="input_nest_current",
            temp_dir="test_nest_current",
            processes=[
                MPIProcess(
                    script_path="nest_elephant_tvb/translation/test_file/input_nest_current/input_current.py",
                    args=[],
                    communication_file="4.txt",
                    background=True
                ),
                MPIProcess(
                    script_path="tests/test_nest_file/step_current_generator_mpi.py",
                    args=[],
                    background=False
                )
            ]
        )
        self.run_test_configuration(config)
    
    def test_translator_nest_to_tvb(self):
        """test_translator_nest_to_tvb.sh 대체"""
        with self.temporary_directory("test_nest_to_tvb_") as temp_dir:
            # 디렉토리 구조 생성
            os.makedirs(os.path.join(temp_dir, "input"))
            os.makedirs(os.path.join(temp_dir, "output"))
            
            # init_spikes.npy 파일 복사 (존재하는 경우)
            init_spikes_src = self.base_dir / "tests" / "init_spikes.npy"
            if init_spikes_src.exists():
                shutil.copy2(init_spikes_src, temp_dir)
            
            config = TestConfiguration(
                name="translator_nest_to_tvb",
                temp_dir=temp_dir,
                processes=[
                    MPIProcess(
                        script_path="nest_elephant_tvb/translation/nest_to_tvb.py",
                        args=[os.path.join(temp_dir, "input/0.txt"), os.path.join(temp_dir, "output/0.txt")],
                        num_processes=2,
                        background=True
                    ),
                    MPIProcess(
                        script_path="nest_elephant_tvb/translation/test_file/test_input_nest_to_tvb.py",
                        args=[os.path.join(temp_dir, "input/0.txt"), "1000.0"],
                        background=True
                    ),
                    MPIProcess(
                        script_path="nest_elephant_tvb/translation/test_file/test_receive_nest_to_tvb.py",
                        args=[os.path.join(temp_dir, "output/0.txt")],
                        background=True
                    )
                ]
            )
            self.run_test_configuration(config)
    
    def test_translator_tvb_to_nest(self):
        """test_translator_tvb_to_nest.sh 대체"""
        with self.temporary_directory("test_tvb_to_nest_") as temp_dir:
            # 디렉토리 구조 생성
            os.makedirs(os.path.join(temp_dir, "translation", "input"))
            os.makedirs(os.path.join(temp_dir, "translation", "output"))
            
            # init_rates.npy 파일 복사 (존재하는 경우)
            init_rates_src = self.base_dir / "tests" / "init_rates.npy"
            if init_rates_src.exists():
                shutil.copy2(init_rates_src, temp_dir)
            
            config = TestConfiguration(
                name="translator_tvb_to_nest",
                temp_dir=temp_dir,
                processes=[
                    MPIProcess(
                        script_path="nest_elephant_tvb/translation/tvb_to_nest.py",
                        args=[os.path.join(temp_dir, "translation/input/0.txt"), os.path.join(temp_dir, "translation/output/0.txt")],
                        num_processes=2,
                        background=True
                    ),
                    MPIProcess(
                        script_path="nest_elephant_tvb/translation/test_file/test_input_tvb_to_nest.py",
                        args=[os.path.join(temp_dir, "translation/input/0.txt"), "1000.0"],
                        background=True
                    ),
                    MPIProcess(
                        script_path="nest_elephant_tvb/translation/test_file/test_receive_tvb_to_nest.py",
                        args=[os.path.join(temp_dir, "translation/output/0.txt")],
                        background=True
                    )
                ]
            )
            self.run_test_configuration(config)
    
    def test_co_simulation(self, mpi_procs: int = 4, threads: int = 4):
        """test_co-sim.sh 대체 (설정 가능한 매개변수)"""
        config = TestConfiguration(
            name=f"co_simulation_{mpi_procs}_{threads}",
            temp_dir="test_co_sim",
            processes=[
                MPIProcess(
                    script_path="tests/run_co-sim_test.py",
                    args=[f"./test_output/", str(mpi_procs), str(threads), "false"],
                    background=False
                )
            ]
        )
        self.run_test_configuration(config)
    
    def test_record_nest_spike(self):
        """test_record_nest_spike.sh 대체"""
        config = TestConfiguration(
            name="record_nest_spike",
            temp_dir="test_nest_record",
            processes=[
                MPIProcess(
                    script_path="nest_elephant_tvb/translation/test_file/record_nest_activity/record_region_activity.py",
                    args=[],
                    communication_file="3.txt",
                    background=True
                ),
                MPIProcess(
                    script_path="nest_elephant_tvb/translation/test_file/record_nest_activity/record_region_activity.py",
                    args=[],
                    communication_file="4.txt",
                    background=True
                ),
                MPIProcess(
                    script_path="tests/test_nest_file/spikedetector_mpi.py",
                    args=[],
                    background=False
                )
            ]
        )
        self.run_test_configuration(config)


def main():
    """Python 테스트 코디네이터의 메인 진입점"""
    coordinator = PythonTestCoordinator()
    
    try:
        # 사용 예시 - shell script 호출을 대체
        if len(sys.argv) > 1:
            test_name = sys.argv[1]
            
            if test_name == "spike":
                coordinator.test_input_nest_spike()
            elif test_name == "current":
                coordinator.test_input_nest_current()
            elif test_name == "translator_n2t":
                coordinator.test_translator_nest_to_tvb()
            elif test_name == "translator_t2n":
                coordinator.test_translator_tvb_to_nest()
            elif test_name == "cosim":
                mpi_procs = int(sys.argv[2]) if len(sys.argv) > 2 else 4
                threads = int(sys.argv[3]) if len(sys.argv) > 3 else 4
                coordinator.test_co_simulation(mpi_procs, threads)
            elif test_name == "record":
                coordinator.test_record_nest_spike()
            else:
                print(f"알 수 없는 테스트: {test_name}")
                print("사용 가능한 테스트: spike, current, translator_n2t, translator_t2n, cosim, record")
        else:
            print("사용법: python3 python_test_coordinator.py <test_name> [args...]")
            print("사용 가능한 테스트:")
            print("  spike           - NEST spike input 테스트")
            print("  current         - NEST current input 테스트")
            print("  translator_n2t  - NEST to TVB translator 테스트")
            print("  translator_t2n  - TVB to NEST translator 테스트")
            print("  cosim [m] [t]   - Co-simulation 테스트 (MPI 프로세스 수, 스레드 수)")
            print("  record          - NEST spike recording 테스트")
    
    finally:
        coordinator.cleanup()


if __name__ == "__main__":
    main()