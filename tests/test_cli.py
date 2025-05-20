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
    assert 'console.log("package1")' not in content[0]
    assert '[core]' not in content[0]
    assert 'Temporary build file' not in content[0]

    # Verify allowed content is present
    assert 'print("Hello, World!")' in content[0]
    assert 'def helper(): pass' in content[0]

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
    assert '[WARNING: Total content exceeded 50 characters]' in content[0]

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

# --- Tests for minify_prompt_text ---
from prompt_gen.cli import minify_prompt_text
import unittest # For structuring tests, pytest will still run them

class TestMinifyPromptText(unittest.TestCase):
    def test_empty_input(self):
        self.assertEqual(minify_prompt_text(""), "")

    def test_excessive_newlines(self):
        self.assertEqual(minify_prompt_text("a\n\n\nb"), "a\n\nb")
        self.assertEqual(minify_prompt_text("a\n\n\n\n\nc"), "a\n\nc")
        self.assertEqual(minify_prompt_text("\n\n\na\n\nb\n\n\n"), "a\n\nb") # Leading/trailing newlines handled by splitlines and join

    def test_leading_trailing_whitespace(self):
        self.assertEqual(minify_prompt_text("  line1  \n\tline2\t"), "line1\nline2")
        self.assertEqual(minify_prompt_text("  \n  line1  \n\tline2\t\n  "), "line1\nline2")


    def test_single_line_comments(self):
        self.assertEqual(minify_prompt_text("# comment\nline1"), "line1")
        self.assertEqual(minify_prompt_text("line1 // comment"), "line1")
        self.assertEqual(minify_prompt_text("  # comment\n  line1  // comment 2"), "line1")
        self.assertEqual(minify_prompt_text("line1  \n# comment\nline2"), "line1\nline2")
        self.assertEqual(minify_prompt_text("line1\n// comment\nline2"), "line1\nline2")

    def test_python_multi_line_comments(self):
        self.assertEqual(minify_prompt_text("'''comment'''\nline1"), "line1") # Assumes comment on its own line, then content
        self.assertEqual(minify_prompt_text('"""comment"""\nline1'), "line1") # Assumes comment on its own line, then content
        # If multiline comment is on its own lines, it results in an empty line preserved by current logic
        self.assertEqual(minify_prompt_text("line1\n'''\nmultiline\ncomment\n'''\nline2"), "line1\n\nline2")
        self.assertEqual(minify_prompt_text("line1\n\"\"\"\nmultiline\ncomment\n\"\"\"\nline2"), "line1\n\nline2")

    def test_c_style_multi_line_comments(self):
        self.assertEqual(minify_prompt_text("/*comment*/\nline1"), "line1") # Assumes comment on its own line, then content
        self.assertEqual(minify_prompt_text("line1\n/*\nmultiline\ncomment\n*/\nline2"), "line1\n\nline2")

    def test_mixed_comment_types(self):
        source = """
        # Python single line
        line1 // C++ single line
        ''' Python multi-line
        comment
        '''
        line2
        /* C-style multi-line
           comment
        */
        line3
        \"\"\"
        Another Python multi-line
        \"\"\"
        """
        # Each multi-line comment block on its own lines will result in one preserved empty line
        expected = "line1\n\nline2\n\nline3" 
        self.assertEqual(minify_prompt_text(source), expected)

    def test_already_minified(self):
        source = "line1\nline2\n\nline3"
        self.assertEqual(minify_prompt_text(source), source)

    def test_comments_in_strings(self):
        # Regex based approach will likely remove comments inside strings. This test acknowledges that.
        source_py = 's = """\nthis is not a comment\n"""\n# but this is'
        expected_py = 's = """\nthis is not a comment\n"""' # The # comment is removed, string preserved
        self.assertEqual(minify_prompt_text(source_py), expected_py)
        
        source_js = 's = `/* this is not a comment */`; // but this is'
        # Current behavior: /*...*/ is removed from string, then // comment is removed.
        expected_js = 's = ``;' 
        self.assertEqual(minify_prompt_text(source_js), expected_js)

        source_c_multiline_in_string = 'const char* str = "/* not a comment */"; /* this is */'
        # Current behavior: first /*...*/ removed from string, second /*...*/ (actual comment) removed.
        expected_c_multiline_in_string = 'const char* str = "";' 
        self.assertEqual(minify_prompt_text(source_c_multiline_in_string), expected_c_multiline_in_string)


    def test_whitespace_and_comments_only(self):
        source = """
        # comment
        // another comment
        /* multi-line
           comment */
        '''
        python multi-line
        '''
        """
        self.assertEqual(minify_prompt_text(source), "")
        
    def test_lines_with_only_whitespace_after_comment_removal(self):
        source = "code # comment\n   \nmore_code" # The middle line ('   ') is originally whitespace.
        # Current logic: "code # comment" -> "code"
        # "   " -> "" (original_line_is_empty_or_whitespace = True, so "" is kept)
        # "more_code" -> "more_code"
        # Result: ["code", "", "more_code"] -> "code\n\nmore_code"
        expected = "code\n\nmore_code" 
        self.assertEqual(minify_prompt_text(source), expected)

# --- Tests for CLI Integration ---
import subprocess
import sys

# Assuming cli.py is in the parent directory of 'tests' or installed
CLI_SCRIPT_PATH = Path(__file__).parent.parent / 'prompt_gen' / 'cli.py'

class TestCLIIntegration(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.test_dir_path = Path(self.test_dir.name)

    def tearDown(self):
        self.test_dir.cleanup()

    def _run_cli(self, args):
        base_command = [sys.executable, str(CLI_SCRIPT_PATH)]
        process = subprocess.run(base_command + args, capture_output=True, text=True, cwd=self.test_dir_path)
        return process

    def _create_file(self, name, content):
        file_path = self.test_dir_path / name
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w') as f:
            f.write(content)
        return file_path

    def test_minify_option_single_file(self):
        file_content = "  line1 # comment  \n\n\n  line2  // comment\n/* block \n comment */ line3"
        expected_minified = "//test_file.py\nline1\n\nline2\nline3" # Note: relative path from cwd of subprocess
        self._create_file("test_file.py", file_content)
        
        process = self._run_cli(['-f', 'test_file.py', '--minify'])
        self.assertEqual(process.returncode, 0)
        # Normalize newlines in output for comparison across platforms
        actual_output = process.stdout.replace('\r\n', '\n').strip()
        # The processing summary is printed to stdout, so we need to find the actual content part
        self.assertTrue(expected_minified in actual_output, f"Expected:\n{expected_minified}\nActual:\n{actual_output}")


    def test_no_minify_option_single_file(self):
        file_content = "  line1 # comment  \n\n\n  line2  // comment\n/* block \n comment */ line3"
        # Expected output will include the "Processing Summary:" etc.
        # We check for the raw content being present.
        # The file path comment should also be unminified if the whole output isn't minified.
        # Current behavior is that file content is NOT minified individually if global minify is off
        
        self._create_file("test_file.py", file_content)
        process = self._run_cli(['-f', 'test_file.py'])
        self.assertEqual(process.returncode, 0)
        actual_output = process.stdout.replace('\r\n', '\n')

        # Check that the original (non-minified) content is part of the output.
        # The read_files prepends "//{file_path}\n" to content
        expected_raw_output_segment = "//test_file.py\n" + file_content
        self.assertTrue(expected_raw_output_segment in actual_output, f"Expected raw segment:\n{expected_raw_output_segment}\nActual output:\n{actual_output}")


    def test_minify_with_save_option(self):
        file_content = "  line_A # comment  \n\n\n  line_B  // comment"
        expected_minified_in_file = "//file_to_save.py\nline_A\n\nline_B"
        
        self._create_file("file_to_save.py", file_content)
        output_save_path = self.test_dir_path / "output.txt"
        
        process = self._run_cli(['-f', 'file_to_save.py', '--minify', '-s', str(output_save_path)])
        self.assertEqual(process.returncode, 0)
        self.assertTrue(output_save_path.exists())
        
        with open(output_save_path, 'r') as f:
            saved_content = f.read().replace('\r\n', '\n').strip()
        self.assertEqual(saved_content, expected_minified_in_file)

    def test_minify_multiple_files(self):
        content1 = "file1 line1 # comment\n\n\nfile1 line2"
        content2 = "  file2 lineA // comment\n/* block */ file2 lineB  "
        self._create_file("f1.txt", content1)
        self._create_file("f2.txt", content2)

        expected_output_segment1 = "//f1.txt\nfile1 line1\n\nfile1 line2"
        expected_output_segment2 = "//f2.txt\nfile2 lineA\nfile2 lineB"
        
        process = self._run_cli(['-f', 'f1.txt', 'f2.txt', '--minify'])
        self.assertEqual(process.returncode, 0)
        actual_output = process.stdout.replace('\r\n', '\n').strip()
        
        self.assertTrue(expected_output_segment1 in actual_output)
        self.assertTrue(expected_output_segment2 in actual_output)
        # Check order and combined output
        # The order of files passed to -f is not guaranteed to be preserved by os.walk or listdir in all cases,
        # though for direct file lists it usually is.
        # For simplicity, we check for inclusion. A more robust test might sort file paths.
        # The final output is minified globally, so the two segments should be joined by \n\n if minify_prompt_text works correctly
        combined_expected = expected_output_segment1 + "\n\n" + expected_output_segment2
        # Check if the combined (and then globally minified) output contains this structure.
        # The global minification might reduce newlines between file contents.
        # Minify function reduces \n{3,} to \n\n.
        # Output structure is: //file1\ncontent1\n//file2\ncontent2
        # If content1 ends with \n\n and content2 starts, it becomes \n\n\n, then minified to \n\n.
        # If content1 ends with \n and content2 starts, it's \n\n.
        # The current `minify_prompt_text` joins lines with `\n` then collapses `\n{3,}` to `\n\n`.
        # The output list has `//filepath` and `content` as separate items.
        # `\n`.join([..., prev_content, '//next_file', next_content, ...])
        # So if prev_content doesn't end with \n, it will be prev_content\n//next_file
        # If prev_content ends with \n, it will be prev_content//next_file (after minify_prompt_text's initial join)
        # This needs careful checking.
        # Current read_files appends `//filepath` and `content` to a list `output`.
        # Then `\n`.join(output).
        # So it's like:
        # //f1.txt
        # file1 line1
        #
        # file1 line2
        # //f2.txt
        # file2 lineA
        # file2 lineB
        # This structure, when passed to `minify_prompt_text`, should have its internal newlines handled correctly.
        # The `\n\n` between `file1 line2` and `//f2.txt` is expected.
        
        self.assertTrue(combined_expected in actual_output, f"Expected combined:\n{combined_expected}\nActual:\n{actual_output}")


    def test_filepath_comment_format_minify(self):
        self._create_file("test.py", "content")
        process = self._run_cli(['-f', 'test.py', '--minify'])
        self.assertEqual(process.returncode, 0)
        actual_output = process.stdout.replace('\r\n', '\n')
        # Path might be absolute or relative depending on how Popen resolves it.
        # The cli.py uses os.path.abspath, but the output is `//{file_path}` where file_path is from all_files_to_process
        # which is constructed from os.path.join(root, file) or the direct path if it's a file.
        # In these tests, we pass relative paths 'test.py'.
        self.assertTrue("//test.py\ncontent" in actual_output)

    def test_filepath_comment_format_no_minify(self):
        self._create_file("test.py", "content")
        process = self._run_cli(['-f', 'test.py'])
        self.assertEqual(process.returncode, 0)
        actual_output = process.stdout.replace('\r\n', '\n')
        self.assertTrue("//test.py\ncontent" in actual_output)
