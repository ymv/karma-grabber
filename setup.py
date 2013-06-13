from setuptools import setup
setup(
    name = "Karma grabber",
    version = "0.0.1",
    packages = ['grab_karma'],
    install_requires=['lxml'],
    entry_points={
        'console_scripts': ['grab_karma = grab_karma:main']
    }
)
