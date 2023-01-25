from setuptools import setup


setup(
    name='pytest-rst',
    version='0.1.0',
    author='Dmitry Orlov',
    author_email='me@mosquito.su',
    license='MIT',
    description='Test code from RST documents with pytest',
    long_description=open("README.rst").read(),
    platforms="all",
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Framework :: Pytest',
        'Intended Audience :: Developers',
        'Natural Language :: Russian',
        'Operating System :: MacOS',
        'Operating System :: POSIX',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: Implementation :: CPython',
    ],
    packages=".",
    install_requires=[
        "pytest",
        "py",
    ],
    entry_points={
        "pytest11": ["pytest-rst = pytest_rst"]
    },
    url='https://github.com/mosquito/pytest-rst'
)
