#!/usr/bin/env python3
"""
Simple Test Runner - YAML 없이도 작동하는 간단한 테스트 러너

PyYAML 의존성 없이 기본 테스트를 실행할 수 있습니다.
"""

import os
import sys
import subprocess
import tempfile
import shutil
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class SimpleProcessConfig:
    """간단한 프로세스 설정"""
    name: str
    script: str
    args: List[str]
    comm_file: Optional[str] = None
    background: bool = True
    mpi_processes: int = 1
    delay: float = 0

class SimpleTestRunner:
    """YAML 없이 작동하는 간단한 테스트 러너"""
    
    def __init__(self):
        self.base_dir = Path.cwd()
        self.logger = self._setup_logging()
        self._setup_environment()
    
    def _setup_logging(self) -> logging.Logger:
        """로깅 설정"""
        logger = logging.getLogger('simple_test_runner')
        logger.setLevel(logging.INFO)
        
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        return logger
    
    def _setup_environment(self):
        """환경 변수 설정"""
        package_path = str(self.base_dir)
        python_lib = str(self.base_dir / "venv" / "lib" / "python3.9" / "site-packages")
        nest_lib = str(self.base_dir / "lib" / "nest_run" / "lib" / "python3.9" / "site-packages")
        
        current_pythonpath = os.environ.get('PYTHONPATH', '')
        new_paths = [package_path, python_lib, nest_lib]
        
        if current_pythonpath:
            os.environ['PYTHONPATH'] = ':'.join(new_paths + [current_pythonpath])
        else:
            os.environ['PYTHONPATH'] = ':'.join(new_paths)
    
    def run_simple_test(self, test_name: str) -> bool:
        """간단한 테스트 실행"""
        
        # 테스트 설정 정의 (하드코딩)
        test_configs = {
            'current': [
                SimpleProcessConfig(
                    name="current_producer",
                    script="nest_elephant_tvb/translation/test_file/input_nest_current/input_current.py",
                    args=[],
                    comm_file="4.txt",
                    background=True,
                    delay=0
                ),
                SimpleProcessConfig(
                    name="current_consumer",
                    script="tests/test_nest_file/step_current_generator_mpi.py",
                    args=[],
                    background=False,
                    delay=0.5
                )
            ],
            
            'spike': [
                SimpleProcessConfig(
                    name="spike_producer",
                    script="nest_elephant_tvb/translation/test_file/spike_nest_input/input_region_activity.py",
                    args=[],
                    comm_file="7.txt",
                    background=True,
                    delay=0
                ),
                SimpleProcessConfig(
                    name="recorder_1",
                    script="nest_elephant_tvb/translation/test_file/record_nest_activity/record_region_activity.py",
                    args=[],
                    comm_file="3.txt",
                    background=True,
                    delay=0.1
                ),
                SimpleProcessConfig(
                    name="recorder_2",
                    script="nest_elephant_tvb/translation/test_file/record_nest_activity/record_region_activity.py",
                    args=[],
                    comm_file="4.txt",
                    background=True,
                    delay=0.2
                ),
                SimpleProcessConfig(
                    name="spike_generator",
                    script="tests/test_nest_file/spikegenerator_mpi.py",
                    args=[],
                    background=False,
                    delay=1.0
                )
            ]
        }
        
        if test_name not in test_configs:
            self.logger.error(f"알 수 없는 테스트: {test_name}")
            return False
        
        processes_config = test_configs[test_name]
        
        # 임시 디렉토리 생성
        with tempfile.TemporaryDirectory(prefix=f"test_{test_name}_") as temp_dir:
            self.logger.info(f"테스트 시작: {test_name}")
            self.logger.info(f"임시 디렉토리: {temp_dir}")
            
            processes = []
            
            # 백그라운드 프로세스 시작
            for config in processes_config:
                if config.background:
                    if config.delay > 0:
                        time.sleep(config.delay)
                    
                    process = self._start_process(config, temp_dir)
                    processes.append(process)
                    self.logger.info(f"백그라운드 프로세스 시작: {config.name}")
            
            # 통신 파일 생성 대기
            time.sleep(1.0)
            
            # 포그라운드 프로세스 실행
            for config in processes_config:
                if not config.background:
                    if config.delay > 0:
                        time.sleep(config.delay)
                    
                    process = self._start_process(config, temp_dir)
                    processes.append(process)
                    self.logger.info(f"포그라운드 프로세스 시작: {config.name}")
            
            # 모든 프로세스 완료 대기
            success = True
            for i, process in enumerate(processes):
                try:
                    stdout, stderr = process.communicate(timeout=60)
                    if process.returncode == 0:
                        self.logger.info(f"프로세스 {i} 성공")
                        if stdout:
                            self.logger.debug(f"STDOUT: {stdout.decode()}")
                    else:
                        self.logger.error(f"프로세스 {i} 실패 (code: {process.returncode})")
                        if stderr:
                            self.logger.error(f"STDERR: {stderr.decode()}")
                        success = False
                except subprocess.TimeoutExpired:
                    self.logger.error(f"프로세스 {i} 타임아웃")
                    process.kill()
                    success = False
            
            self.logger.info(f"테스트 완료: {test_name} ({'성공' if success else '실패'})")
            return success
    
    def _start_process(self, config: SimpleProcessConfig, temp_dir: str) -> subprocess.Popen:
        """프로세스 시작"""
        cmd = [
            'mpirun',
            '-n', str(config.mpi_processes),
            'python3',
            str(self.base_dir / config.script)
        ]
        
        # 인수 추가
        cmd.extend(config.args)
        
        # 통신 파일 추가
        if config.comm_file:
            comm_path = os.path.join(temp_dir, config.comm_file)
            cmd.append(comm_path)
        
        self.logger.debug(f"실행 명령: {' '.join(cmd)}")
        
        return subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

def main():
    """메인 함수"""
    runner = SimpleTestRunner()
    
    if len(sys.argv) < 2:
        print("사용법: python3 simple_test_runner.py <test_name>")
        print("사용 가능한 테스트: current, spike")
        return
    
    test_name = sys.argv[1]
    success = runner.run_simple_test(test_name)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()