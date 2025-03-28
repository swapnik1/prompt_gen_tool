import os
import pytest
import tempfile
import shutil
from pathlib import Path

from prompt_gen.cli import ProjectContextReader

@pytest.fixture
def temp_project_structure():
    """
    Create a temporary project structure for testing
    """
    # Create a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create project structure
        structure = {
            'src': {
                'main.py': 'print("Hello, World!")',
                'utils': {
                    'helper.py': 'def helper(): pass',
                },
                'tests': {
                    'test_main.py': 'def test_main(): pass',
                },
            },
            'node_modules': {
                'package1': {
                    'index.js': 'console.log("package1");'
                }
            },
            '.git': {
                'config': '[core]\n\trepositoryformatversion = 0'
            },
            '.gitignore': '*/*.log\n*.pyc',
            'README.md': '# Project README',
            'build': {
                'temp.txt': 'Temporary build file'
            }
        }

        # Recursively create directory structure
        def create_structure(base_path, structure):
            for name, content in structure.items():
                path = os.path.join(base_path, name)
                if isinstance(content, dict):
                    os.makedirs(path, exist_ok=True)
                    create_structure(path, content)
                else:
                    with open(path, 'w') as f:
                        f.write(content)

        create_structure(temp_dir, structure)
        yield temp_dir

def test_should_exclude_basic(temp_project_structure):
    """
    Test basic exclusion functionality
    """
    reader = ProjectContextReader()

    # Test excluding entire directories
    assert reader._should_exclude(
        os.path.join(temp_project_structure, 'node_modules'),
        {'node_modules'}
    )

    # Test excluding nested files in excluded directory
    assert reader._should_exclude(
        os.path.join(temp_project_structure, 'node_modules', 'package1', 'index.js'),
        {'node_modules'}
    ), "Nested file in excluded directory should be excluded"

def test_should_exclude_with_wildcard(temp_project_structure):
    """
    Test exclusion with wildcard patterns
    """
    reader = ProjectContextReader()

    # Test wildcard exclusions for .git directory
    assert reader._should_exclude(
        os.path.join(temp_project_structure, '.git', 'config'),
        {'.git*'}
    ), "Files in .git directory should be excluded with .git* pattern"

    # Test nested directory wildcard exclusion
    assert reader._should_exclude(
        os.path.join(temp_project_structure, 'src', 'tests', 'test_main.py'),
        {'**/tests/*'}
    ), "Nested files should be excluded with wildcard pattern"

def test_project_structure_exclusion(temp_project_structure):
    """
    Test project structure generation with exclusions
    """
    reader = ProjectContextReader()

    # Generate project structure with exclusions
    structure = reader.display_project_structure(
        [temp_project_structure],
        exclude_patterns={'node_modules', '.git', 'build'}
    )

    # Check excluded directories are not present
    assert 'node_modules/' not in structure
    assert '.git/' not in structure
    assert 'build/' not in structure

    # Check remaining directories are present
    assert 'src/' in structure
    assert 'README.md' in structure

def test_read_files_exclusion(temp_project_structure):
    """
    Test reading files with exclusions
    """
    reader = ProjectContextReader()

    # Read files with exclusions
    content = reader.read_files(
        [temp_project_structure],
        exclude_patterns={'node_modules', '.git', 'build'}
    )

    # Verify excluded content is not present
    assert 'console.log("package1")' not in content
    assert '[core]' not in content
    assert 'Temporary build file' not in content

    # Verify allowed content is present
    assert 'print("Hello, World!")' in content
    assert 'def helper(): pass' in content

def test_max_depth_limitation(temp_project_structure):
    """
    Test maximum directory depth limitation
    """
    reader = ProjectContextReader()

    # Generate project structure with max depth 1
    structure = reader.display_project_structure(
        [temp_project_structure],
        max_depth=1
    )

    # Check only top-level and first-level directories are present
    assert 'src/' in structure
    assert 'node_modules/' in structure
    assert '.git/' in structure

    # Ensure deeper levels are not shown
    assert 'src/utils/' not in structure
    assert 'src/tests/' not in structure

def test_input_limit(temp_project_structure):
    """
    Test input length limitation
    """
    reader = ProjectContextReader(input_limit=50)

    # Read files with low input limit
    content = reader.read_files(
        [temp_project_structure],
        exclude_patterns={'node_modules', '.git', 'build'}
    )

    # Verify warning is added when content exceeds limit
    assert '[WARNING: Total content exceeded 50 characters]' in content

def test_file_size_limitation(temp_project_structure):
    """
    Test file size limitation
    """
    reader = ProjectContextReader(max_file_size=10)

    # Read files with small max file size
    content = reader.read_files([temp_project_structure])

    # Check skipped files summary
    assert len(reader.skipped_files) > 0
    assert any('File too large' in str(reason) for _, reason in reader.skipped_files)

# Additional helper to run all tests
def test_cli_integration():
    """
    Placeholder for potential CLI integration tests
    Can be expanded to test actual command-line interface
    """
    # TODO: Implement CLI integration tests
    pass
