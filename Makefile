# TVB-NEST Enhanced Orchestrator - Development & Testing
# Usage: make <target>

.PHONY: help dev test test-watch clean build docs lint

# Default target
help: ## Show this help message
	@echo "🚀 TVB-NEST Enhanced Orchestrator - Development Commands"
	@echo "================================================================"
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
	@echo ""
	@echo "📊 Quick Status:"
	@echo "  Dev Container: $$(docker-compose -f docker-compose.dev.yml ps --services --filter status=running 2>/dev/null || echo 'Not running')"
	@echo ""

# Development environment
dev: ## Start development environment with Jupyter Lab
	@echo "🚀 Starting TVB-NEST development environment..."
	docker-compose -f docker-compose.dev.yml up -d
	@echo "✅ Jupyter Lab available at http://localhost:8889"

dev-build: ## Build development Docker image
	@echo "🏗️ Building TVB-NEST development image..."
	docker-compose -f docker-compose.dev.yml build

dev-logs: ## Show development container logs
	docker-compose -f docker-compose.dev.yml logs -f

dev-sh: ## Access development container shell
	@echo "🐚 Accessing development container shell..."
	docker exec -it tvb-nest-dev bash

dev-stop: ## Stop development environment
	@echo "🛑 Stopping development environment..."
	docker-compose -f docker-compose.dev.yml down

# Testing
test: ## Run all orchestrator tests with optimal settings
	@echo "🧪 Running TVB-NEST Enhanced Orchestrator Tests..."
	@echo "================================================================"
	docker-compose -f docker-compose.dev.yml --profile test run --rm tvb-nest-test

test-fast: ## Run tests on existing dev container (faster, less verbose)
	@echo "⚡ Running tests on existing dev container..."
	@docker exec tvb-nest-dev bash -c "cd /home && python3 -m pytest nest_elephant_tvb/orchestrator/tests/ --tb=line --no-header -q --color=yes"

test-verbose: ## Run tests with maximum verbosity and detailed output
	@echo "🔍 Running tests with verbose output..."
	@docker exec tvb-nest-dev bash -c "cd /home && python3 -m pytest nest_elephant_tvb/orchestrator/tests/ -vvv --tb=long --color=yes --capture=no -s"

test-summary: ## Run tests with clean summary output (recommended for CI)
	@echo "📊 Running tests with summary output..."
	@docker exec tvb-nest-dev bash -c "cd /home && python3 -m pytest nest_elephant_tvb/orchestrator/tests/ --tb=short --no-header --color=yes -q --disable-warnings"

test-watch: ## Run tests in watch mode with optimized output
	@echo "👀 Running tests in watch mode (Ctrl+C to stop)..."
	@docker exec tvb-nest-dev bash -c "cd /home && python3 -m pytest nest_elephant_tvb/orchestrator/tests/ -f --tb=line --color=yes -q"

test-debug: ## Run tests with debugging information (no capture, full traceback)
	@echo "🐛 Running tests in debug mode..."
	@docker exec tvb-nest-dev bash -c "cd /home && python3 -m pytest nest_elephant_tvb/orchestrator/tests/ -vs --tb=long --capture=no --color=yes --pdb-trace"

test-specific: ## Run specific test file (Usage: make test-specific FILE=test_experiment_builder.py)
	@echo "🎯 Running specific test: $(FILE)"
	@docker exec tvb-nest-dev bash -c "cd /home && python3 -m pytest nest_elephant_tvb/orchestrator/tests/$(FILE) -v --tb=short --color=yes"

test-class: ## Run specific test class (Usage: make test-class CLASS=TestExperimentBuilder)
	@echo "🎯 Running test class: $(CLASS)"
	@docker exec tvb-nest-dev bash -c "cd /home && python3 -m pytest nest_elephant_tvb/orchestrator/tests/ -k '$(CLASS)' -v --tb=short --color=yes"

test-keyword: ## Run tests matching keyword (Usage: make test-keyword KEYWORD=builder)
	@echo "🔍 Running tests matching keyword: $(KEYWORD)"
	@docker exec tvb-nest-dev bash -c "cd /home && python3 -m pytest nest_elephant_tvb/orchestrator/tests/ -k '$(KEYWORD)' -v --tb=short --color=yes"

test-failed: ## Re-run only failed tests from last run
	@echo "🔄 Re-running failed tests..."
	@docker exec tvb-nest-dev bash -c "cd /home && python3 -m pytest nest_elephant_tvb/orchestrator/tests/ --lf --tb=short --color=yes -v"

test-coverage: ## Run tests with coverage report
	@echo "📊 Running tests with coverage..."
	@docker exec tvb-nest-dev bash -c "cd /home && python3 -m pytest nest_elephant_tvb/orchestrator/tests/ --cov=nest_elephant_tvb.orchestrator --cov-report=term-missing --cov-report=html --cov-fail-under=80 --tb=short --color=yes"

test-performance: ## Run tests with performance timing
	@echo "⏱️ Running tests with performance timing..."
	@docker exec tvb-nest-dev bash -c "cd /home && python3 -m pytest nest_elephant_tvb/orchestrator/tests/ --durations=10 --tb=short --color=yes -v"

test-parallel: ## Run tests in parallel (if pytest-xdist is available)
	@echo "🚀 Running tests in parallel..."
	@docker exec tvb-nest-dev bash -c "cd /home && python3 -m pytest nest_elephant_tvb/orchestrator/tests/ -n auto --tb=short --color=yes" || echo "⚠️ Install pytest-xdist for parallel testing"

test-markers: ## Show available test markers
	@echo "🏷️ Available test markers:"
	@docker exec tvb-nest-dev bash -c "cd /home && python3 -m pytest --markers" | grep -A 1 "@pytest.mark" || echo "No custom markers defined"

# Legacy shell tests
test-shell: ## Run legacy shell script tests
	@echo "🐚 Running legacy shell script tests..."
	@docker exec tvb-nest-dev bash -c "cd /home && ./tests/test_co-sim.sh"

test-yaml: ## Run YAML-based tests (alternative to shell scripts)
	@echo "📄 Running YAML-based tests..."
	@docker exec tvb-nest-dev bash -c "cd /home && python3 tests/python_runners/yaml_test_runner.py list && python3 tests/python_runners/yaml_test_runner.py test_input_nest_current"

# Development utilities
lint: ## Run code linting (if dev container is running)
	@echo "🔍 Running code linting..."
	@docker exec tvb-nest-dev bash -c "cd /home && python3 -m flake8 nest_elephant_tvb/orchestrator/ --max-line-length=120 --extend-ignore=E203,W503" || echo "⚠️ Linting requires flake8 to be installed"

clean: ## Clean up Docker containers and volumes
	@echo "🧹 Cleaning up Docker containers..."
	docker-compose -f docker-compose.dev.yml down -v
	docker system prune -f

build-prod: ## Build production Docker images
	@echo "🏭 Building production Docker images..."
	./install/docker/create_docker_2.sh

# CI/CD and verification
verify: test ## Alias for test - verify all functionality works
	@echo "✅ Verification complete!"

ci: ## Run full CI pipeline (build + test)
	@echo "🔄 Running CI pipeline..."
	$(MAKE) dev-build
	$(MAKE) test
	@echo "✅ CI pipeline complete!"

# Examples and usage
examples: ## Run usage examples
	@echo "📚 Running usage examples..."
	@docker exec tvb-nest-dev bash -c "cd /home && python3 -c 'from nest_elephant_tvb.orchestrator.tests.test_usage_examples import TestUsageExamples; t = TestUsageExamples(); print(\"🎯 Running traditional workflow example...\"); t.test_traditional_workflow_example(); print(\"✅ Example completed successfully!\")'"

demo: ## Run a quick demo of the enhanced orchestrator
	@echo "🎬 TVB-NEST Enhanced Orchestrator Demo"
	@echo "======================================"
	@docker exec tvb-nest-dev bash -c "cd /home && python3 -c 'import types; from nest_elephant_tvb.orchestrator.experiment_builder import ExperimentBuilder; from nest_elephant_tvb.orchestrator.tests.test_usage_examples import create_example_parameter_module; print(\"📊 Creating experiment with Builder pattern...\"); param_module = create_example_parameter_module(); experiment = ExperimentBuilder().with_base_parameters(param_module).with_results_path(\"/tmp/demo/\").explore_parameter(\"g\", [1.0, 1.5]).with_experiment_name(\"Demo Experiment\").build(); info = experiment.get_experiment_info(); print(f\"✅ Experiment created: {info[\"name\"]} with {info[\"num_parameter_combinations\"]} combinations\"); print(\"🎉 Enhanced orchestrator working correctly!\")'"

# Status and information
status: ## Show development environment status
	@echo "📊 TVB-NEST Development Environment Status"
	@echo "========================================="
	@echo "Docker Containers:"
	@docker-compose -f docker-compose.dev.yml ps
	@echo ""
	@echo "Docker Images:"
	@docker images | grep tvb-nest || echo "No TVB-NEST images found"
	@echo ""
	@echo "Available Services:"
	@echo "  🔬 Jupyter Lab: http://localhost:8889 (if dev container running)"
	@echo "  🧪 Test Runner: make test"
	@echo "  🐚 Shell Access: make dev-shell"

# Documentation
docs: ## Generate or view documentation
	@echo "📖 Documentation Commands"
	@echo "========================"
	@echo "📁 Project Structure:"
	@echo "  📂 nest_elephant_tvb/orchestrator/ - Enhanced orchestrator implementation"
	@echo "  📂 nest_elephant_tvb/orchestrator/tests/ - Pytest test suite"
	@echo "  📂 tests/ - Legacy shell script tests + Python alternatives"
	@echo "  📂 examples/ - Usage examples and demonstrations"
	@echo ""
	@echo "🧪 Test Files:"
	@find nest_elephant_tvb/orchestrator/tests/ -name "test_*.py" -exec basename {} \; | sort
	@echo ""
	@echo "📚 Key Features:"
	@echo "  • Builder pattern for experiment configuration"
	@echo "  • Pydantic validation with legacy fallback"
	@echo "  • Module object support (example.parameter.test_nest)"
	@echo "  • Parameter exploration and linking (TVB↔NEST)"
	@echo "  • 100% backward compatibility"