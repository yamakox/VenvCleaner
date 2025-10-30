from pathlib import Path
import shutil
import subprocess
import os

package_list = [
    'numpy',
    'pandas',
    'matplotlib',
    'seaborn',
    'scikit-learn',
    'scipy',
    'pillow',
    'jupyterlab',
    'tensorflow',
    'wxPython',
]
test_number = 5     # 0 is for removing all test venvs

base_path = Path('/tmp/venv_cleaner_test')
print(f'Removing {base_path}...')
shutil.rmtree(base_path, ignore_errors=True)

env = os.environ.copy()
del env['VIRTUAL_ENV']

for i in range(test_number):
    test_name = f'test-set-{i + 1}'
    test_path = base_path / test_name
    for j in range(len(package_list)):
        if i % 2 == 1:
            project_name = f'example {package_list[j]} project'
        else:
            project_name = f'example-{package_list[j]}-project'
        path = test_path / project_name
        print(f'Creating venv {path}...')
        try:
            path.mkdir(parents=True)
            subprocess.run(['uv', 'init'], cwd=path, env=env)
            subprocess.run(['uv', 'add'] + package_list[:j + 1], cwd=path, env=env)
        except Exception as e:
            print(f'Error creating venv {path}: {e}')

print(f'Test venvs finished in {base_path}')
