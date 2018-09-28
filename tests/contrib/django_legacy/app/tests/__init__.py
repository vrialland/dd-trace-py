import os

"""
Django 1.4 will import all test cases from this module so we have to import and
expose all the test cases.
"""

for module in os.listdir(os.path.dirname(__file__)):
    if module == '__init__.py' or module[-3:] != '.py':
        continue
    __import__(module[:-3], locals(), globals())
del module
