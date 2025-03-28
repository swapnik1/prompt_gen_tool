from setuptools import setup, find_packages

setup(
    name='prompt_gen',
    version='0.1.0',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'prompt-gen = prompt_gen.cli:run',
        ],
    },
    description='A CLI tool to output contents of files in a directory or specified paths.',
    author='Swapnik Shah',
    author_email='your_email@example.com',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6',
)
