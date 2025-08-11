#!/usr/bin/env python3
"""
Module import testing script for TVB-NEST environment.
Tests critical and optional module imports with detailed error reporting.
"""
import sys
import importlib

def test_module_imports():
    """Test critical and optional module imports."""
    print(f'Python: {sys.version}')
    
    # Track critical import failures
    critical_failures = []
    optional_failures = []
    
    # Critical imports
    critical_modules = [
        ('nest', 'NEST simulator'),
        ('numpy', 'NumPy'),
        ('scipy', 'SciPy'), 
        ('matplotlib', 'Matplotlib'),
        ('elephant', 'Elephant'),
        ('networkx', 'NetworkX'),
        ('pandas', 'Pandas'),
    ]
    
    for module_name, display_name in critical_modules:
        try:
            module = importlib.import_module(module_name)
            version = getattr(module, '__version__', 'OK')
            print(f'✅ {display_name}: {version}')
        except ImportError as e:
            critical_failures.append(f'{display_name}: {e}')
            print(f'❌ {display_name} import failed: {e}')
    
    # Optional imports
    optional_modules = [
        ('tvb', 'TVB'),
        ('numba', 'Numba'),
        ('elephant', 'Elephant')
    ]
    
    for module_name, display_name in optional_modules:
        try:
            module = importlib.import_module(module_name)
            version = getattr(module, '__version__', 'OK')
            print(f'✅ {display_name}: {version}')
        except ImportError as e:
            optional_failures.append(f'{display_name}: {e}')
            print(f'⚠️ {display_name} import failed: {e} (optional)')
    
    # Summary
    if critical_failures:
        print(f'\n❌ {len(critical_failures)} critical import(s) failed!')
        for failure in critical_failures:
            print(f'  - {failure}')
        return 1
    elif optional_failures:
        print(f'\n⚠️ {len(optional_failures)} optional import(s) failed')
        print('✅ All critical modules imported successfully')
        return 0
    else:
        print('\n✅ All modules imported successfully')
        return 0

if __name__ == '__main__':
    sys.exit(test_module_imports())