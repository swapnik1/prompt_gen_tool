from setuptools import setup, find_packages

setup(
    name='prompt_gen',
    version='0.1.0',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'prompt-gen=prompt_gen.cli:main',  # Corrected entry point
        ],
    },
    description='A CLI tool to output contents of files in a directory or specified paths.',
    long_description=open('README.md').read() if open('README.md').read() else '',
    long_description_content_type='text/markdown',
    author='Swapnik Shah',
    author_email='your_email@example.com',
    url='https://github.com/yourusername/prompt-gen',  # Add your project's repository URL
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6',
    install_requires=[
        'PyYAML',
        'chardet'
    ],
    keywords='cli tool project context file reader',
	extras_require={
        'test': [
            'pytest',
            'pytest-cov',  # Optional: for coverage reporting
        ]
    },
    tests_require=[
        'pytest',
    ],
    test_suite='tests',
)
