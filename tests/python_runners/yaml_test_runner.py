#!/usr/bin/env python3
"""
YAML Test Runner - Declarative Test Configuration System

이 모듈은 YAML 설정 파일을 기반으로 MPI 테스트를 실행하는 시스템입니다.
Shell script의 imperative한 방식을 declarative YAML 설정으로 대체합니다.
"""

import os
import sys
import yaml
import subprocess
import tempfile
import shutil
import time
import threading
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from contextlib import contextmanager
import asyncio
import concurrent.futures

@dataclass
class ProcessConfig:
    """프로세스 설정"""
    name: str
    description: str
    script: str
    mpi_processes: int = 1
    arguments: List[str] = field(default_factory=list)
    communication: Dict[str, Any] = field(default_factory=dict)
    execution: Dict[str, Any] = field(default_factory=dict)
    
@dataclass 
class TestConfig:
    """전체 테스트 설정"""
    name: str
    description: str
    version: str
    environment: Dict[str, Any]
    setup: Dict[str, Any]
    processes: List[ProcessConfig]
    validation: Dict[str, Any] = field(default_factory=dict)
    logging: Dict[str, Any] = field(default_factory=dict)
    test_matrix: Dict[str, Any] = field(default_factory=dict)

class YAMLTestRunner:
    """YAML 기반 테스트 러너"""
    
    def __init__(self, config_dir: str = "tests/config"):
        self.base_dir = Path.cwd()
        self.config_dir = Path(config_dir)
        self.temp_dirs = []
        self.running_processes = []
        self.logger = self._setup_logging()
        
        # 환경 설정
        self._setup_environment()
    
    def _setup_logging(self) -> logging.Logger:
        """로깅 시스템 설정"""
        logger = logging.getLogger('yaml_test_runner')
        logger.setLevel(logging.INFO)
        
        # 콘솔 핸들러
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        return logger
    
    def _setup_environment(self):
        """환경 변수 설정"""
        # PYTHONPATH 설정 (init.sh와 동등)
        package_path = str(self.base_dir)
        python_lib = str(self.base_dir / "venv" / "lib" / "python3.9" / "site-packages")
        nest_lib = str(self.base_dir / "lib" / "nest_run" / "lib" / "python3.9" / "site-packages")
        
        current_pythonpath = os.environ.get('PYTHONPATH', '')
        new_paths = [package_path, python_lib, nest_lib]
        
        if current_pythonpath:
            os.environ['PYTHONPATH'] = ':'.join(new_paths + [current_pythonpath])
        else:
            os.environ['PYTHONPATH'] = ':'.join(new_paths)
    
    def load_test_config(self, config_file: str) -> TestConfig:
        """YAML 설정 파일 로드"""
        config_path = self.config_dir / f"{config_file}.yaml"
        
        if not config_path.exists():
            raise FileNotFoundError(f"설정 파일을 찾을 수 없습니다: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            yaml_data = yaml.safe_load(f)
        
        # 설정 검증 및 변환
        return self._parse_test_config(yaml_data)
    
    def _parse_test_config(self, yaml_data: Dict[str, Any]) -> TestConfig:
        """YAML 데이터를 TestConfig 객체로 변환"""
        processes = []
        for proc_data in yaml_data.get('processes', []):
            process = ProcessConfig(
                name=proc_data['name'],
                description=proc_data.get('description', ''),
                script=proc_data['script'],
                mpi_processes=proc_data.get('mpi', {}).get('processes', 1),
                arguments=proc_data.get('arguments', []),
                communication=proc_data.get('communication', {}),
                execution=proc_data.get('execution', {})
            )
            processes.append(process)
        
        return TestConfig(
            name=yaml_data['name'],
            description=yaml_data.get('description', ''),
            version=yaml_data.get('version', '1.0'),
            environment=yaml_data.get('environment', {}),
            setup=yaml_data.get('setup', {}),
            processes=processes,
            validation=yaml_data.get('validation', {}),
            logging=yaml_data.get('logging', {}),
            test_matrix=yaml_data.get('test_matrix', {})
        )
    
    @contextmanager
    def test_environment(self, config: TestConfig):
        """테스트 환경 생성 및 정리"""
        # 임시 디렉토리 생성 - NEST 테스트의 경우 tests 디렉토리 내에 생성
        temp_prefix = config.environment.get('temp_directory_prefix', 'test_')
        base_directory = config.environment.get('base_directory', str(self.base_dir))
        
        if base_directory == "/home/tests":
            # Docker 환경에서 tests 디렉토리 내에 임시 디렉토리 생성
            tests_dir = self.base_dir / "tests"
            temp_dir = str(tests_dir / temp_prefix)
            os.makedirs(temp_dir, exist_ok=True)
        else:
            temp_dir = tempfile.mkdtemp(prefix=f"{temp_prefix}_")
        
        self.temp_dirs.append(temp_dir)
        
        try:
            # 디렉토리 구조 생성
            setup_config = config.setup
            for dir_path in setup_config.get('create_directories', []):
                if dir_path == 'temp_directory':
                    continue  # 이미 생성됨
                full_path = Path(temp_dir) / dir_path.format(temp_directory=temp_dir)
                full_path.mkdir(parents=True, exist_ok=True)
            
            # 파일 복사
            for file_config in setup_config.get('copy_files', []):
                src = Path(file_config['source'])
                dst_path = file_config['destination'].format(temp_directory=temp_dir)
                dst = Path(dst_path)
                
                if src.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                elif file_config.get('required', True):
                    raise FileNotFoundError(f"필수 파일을 찾을 수 없습니다: {src}")
            
            # 로그 파일 설정
            if config.logging.get('file'):
                log_file = config.logging['file'].format(temp_directory=temp_dir)
                log_path = Path(log_file)
                log_path.parent.mkdir(parents=True, exist_ok=True)
                
                # 파일 핸들러 추가
                file_handler = logging.FileHandler(log_file)
                file_formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
                file_handler.setFormatter(file_formatter)
                self.logger.addHandler(file_handler)
            
            yield temp_dir
            
        finally:
            # 정리
            if setup_config.get('cleanup_on_exit', True):
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                    if temp_dir in self.temp_dirs:
                        self.temp_dirs.remove(temp_dir)
    
    def _resolve_arguments(self, args: List[str], temp_dir: str, matrix_config: Dict = None) -> List[str]:
        """인수 템플릿 해결"""
        resolved_args = []
        for arg in args:
            resolved_arg = arg.replace('{temp_directory}', temp_dir)
            if matrix_config:
                for key, value in matrix_config.items():
                    resolved_arg = resolved_arg.replace(f'{{matrix.{key}}}', str(value))
            resolved_args.append(resolved_arg)
        return resolved_args
    
    async def run_process_async(self, process_config: ProcessConfig, temp_dir: str, 
                              matrix_config: Dict = None) -> subprocess.CompletedProcess:
        """비동기적으로 프로세스 실행"""
        mpi_cmd = process_config.execution.get('mpi_command', 'mpirun')
        if matrix_config and 'mpi_processes' in matrix_config:
            num_processes = matrix_config['mpi_processes']
        else:
            num_processes = process_config.mpi_processes
        
        # 작업 디렉토리 결정 - NEST 스크립트의 경우 /home/tests 에서 실행
        working_dir = str(self.base_dir)
        if 'test_nest_file' in process_config.script:
            working_dir = str(self.base_dir / "tests")
        
        # 명령어 구성
        cmd = [
            mpi_cmd,
            '-n', str(num_processes),
            'python3'
        ]
        
        # 스크립트 경로를 작업 디렉토리 기준으로 조정
        if working_dir == str(self.base_dir / "tests"):
            # tests 디렉토리에서 실행하는 경우 상대 경로 사용
            if process_config.script.startswith('tests/'):
                script_path = process_config.script[6:]  # 'tests/' 제거
            else:
                script_path = f"../{process_config.script}"
        else:
            script_path = process_config.script
        
        cmd.append(script_path)
        
        # 인수 추가
        resolved_args = self._resolve_arguments(process_config.arguments, temp_dir, matrix_config)
        cmd.extend(resolved_args)
        
        # 통신 파일 추가 - NEST가 찾을 수 있는 위치에 생성
        comm_config = process_config.communication
        if comm_config.get('type') == 'file' and comm_config.get('file'):
            if working_dir == str(self.base_dir / "tests"):
                # NEST 프로세스의 경우 tests 디렉토리 내에 통신 파일 생성
                comm_file = os.path.join(temp_dir, comm_config['file'])
            else:
                # 다른 프로세스의 경우도 동일한 위치 사용
                comm_file = os.path.join(temp_dir, comm_config['file'])
            cmd.append(comm_file)
        
        self.logger.info(f"프로세스 시작 [{process_config.name}] in {working_dir}: {' '.join(cmd)}")
        
        # 시작 지연
        start_delay = process_config.execution.get('start_delay', 0)
        if start_delay > 0:
            await asyncio.sleep(start_delay)
        
        # 프로세스 실행
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=working_dir
        )
        
        stdout, stderr = await process.communicate()
        
        result = subprocess.CompletedProcess(
            cmd, process.returncode, stdout, stderr
        )
        
        # 결과 로깅
        if result.returncode == 0:
            self.logger.info(f"프로세스 성공 [{process_config.name}]")
            if stdout:
                self.logger.debug(f"STDOUT: {stdout.decode()}")
        else:
            self.logger.error(f"프로세스 실패 [{process_config.name}] (code: {result.returncode})")
            if stderr:
                self.logger.error(f"STDERR: {stderr.decode()}")
        
        return result
    
    async def run_test_configuration_async(self, config: TestConfig, matrix_config: Dict = None):
        """비동기적으로 테스트 설정 실행"""
        with self.test_environment(config) as temp_dir:
            self.logger.info(f"테스트 시작: {config.name}")
            if matrix_config:
                self.logger.info(f"매트릭스 설정: {matrix_config}")
            
            # 프로세스들을 실행 모드별로 분류
            background_processes = [p for p in config.processes if p.execution.get('mode') == 'background']
            foreground_processes = [p for p in config.processes if p.execution.get('mode') != 'background']
            
            # 백그라운드 프로세스 시작
            background_tasks = []
            for process_config in background_processes:
                task = asyncio.create_task(
                    self.run_process_async(process_config, temp_dir, matrix_config)
                )
                background_tasks.append(task)
            
            # 동기화 지연
            sync_delay = config.environment.get('synchronization_delay', 1.0)  
            await asyncio.sleep(sync_delay)
            
            # 포그라운드 프로세스 실행
            foreground_results = []
            for process_config in foreground_processes:
                result = await self.run_process_async(process_config, temp_dir, matrix_config)
                foreground_results.append(result)
            
            # 백그라운드 프로세스 완료 대기
            if background_tasks:
                background_results = await asyncio.gather(*background_tasks, return_exceptions=True)
            else:
                background_results = []
            
            # 검증
            success = self._validate_test_results(config, foreground_results + background_results, temp_dir)
            
            self.logger.info(f"테스트 완료: {config.name} ({'성공' if success else '실패'})")
            return success
    
    def _validate_test_results(self, config: TestConfig, results: List, temp_dir: str) -> bool:
        """테스트 결과 검증"""
        validation_config = config.validation
        success_criteria = validation_config.get('success_criteria', {})
        
        # 모든 프로세스가 성공적으로 종료되었는지 확인
        if success_criteria.get('all_processes_exit_zero', False):
            for result in results:
                if isinstance(result, subprocess.CompletedProcess) and result.returncode != 0:
                    self.logger.error(f"프로세스 실패 감지: return code {result.returncode}")
                    return False
        
        # 통신 파일이 생성되었는지 확인
        comm_files = success_criteria.get('communication_files_created', [])
        for comm_file in comm_files:
            file_path = Path(temp_dir) / comm_file
            if not file_path.exists():
                self.logger.error(f"통신 파일이 생성되지 않음: {comm_file}")
                return False
        
        return True
    
    def run_test(self, test_name: str):
        """테스트 실행 (동기 인터페이스)"""
        try:
            config = self.load_test_config(test_name)
            
            # 매트릭스 테스트인지 확인
            if config.test_matrix and 'configurations' in config.test_matrix:
                return self._run_matrix_test(config)
            else:
                return asyncio.run(self.run_test_configuration_async(config))
                
        except Exception as e:
            self.logger.error(f"테스트 실행 중 오류: {e}")
            return False
    
    def _run_matrix_test(self, config: TestConfig) -> bool:
        """매트릭스 테스트 실행"""
        configurations = config.test_matrix['configurations']
        all_success = True
        
        for matrix_config in configurations:
            self.logger.info(f"매트릭스 설정 실행: {matrix_config['name']}")
            success = asyncio.run(self.run_test_configuration_async(config, matrix_config))
            if not success:
                all_success = False
                self.logger.error(f"매트릭스 설정 실패: {matrix_config['name']}")
        
        return all_success
    
    def list_available_tests(self) -> List[str]:
        """사용 가능한 테스트 목록 반환"""
        if not self.config_dir.exists():
            return []
        
        tests = []
        for yaml_file in self.config_dir.glob("*.yaml"):
            test_name = yaml_file.stem
            tests.append(test_name)
        
        return sorted(tests)
    
    def cleanup(self):
        """리소스 정리"""
        for process in self.running_processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
        
        for temp_dir in self.temp_dirs:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)


def main():
    """메인 진입점"""
    runner = YAMLTestRunner()
    
    try:
        if len(sys.argv) < 2:
            print("사용법: python3 yaml_test_runner.py <test_name>")
            print("\n사용 가능한 테스트:")
            for test in runner.list_available_tests():
                print(f"  {test}")
            return
        
        test_name = sys.argv[1]
        
        if test_name == "list":
            print("사용 가능한 테스트:")
            for test in runner.list_available_tests():
                print(f"  {test}")
            return
        
        success = runner.run_test(test_name)
        
        if success:
            print(f"✅ 테스트 '{test_name}' 성공")
            sys.exit(0)
        else:
            print(f"❌ 테스트 '{test_name}' 실패")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n테스트가 사용자에 의해 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"오류: {e}")
        sys.exit(1)
    finally:
        runner.cleanup()


if __name__ == "__main__":
    main()