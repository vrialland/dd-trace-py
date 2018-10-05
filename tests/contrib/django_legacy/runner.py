import unittest
import os
from importlib import import_module
import logging

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, SimpleTestCase
from django.test.utils import setup_test_environment, teardown_test_environment
from django.test.simple import DjangoTestSuiteRunner

from collections import OrderedDict


class OrderedSet(object):
    """
    A set which keeps the ordering of the inserted items.
    Currently backs onto OrderedDict.
    """

    def __init__(self, iterable=None):
        self.dict = OrderedDict(((x, None) for x in iterable) if iterable else [])

    def add(self, item):
        self.dict[item] = None

    def remove(self, item):
        del self.dict[item]

    def discard(self, item):
        try:
            self.remove(item)
        except KeyError:
            pass

    def __iter__(self):
        return iter(self.dict.keys())

    def __contains__(self, item):
        return item in self.dict

    def __bool__(self):
        return bool(self.dict)

    def __nonzero__(self):      # Python 2 compatibility
        return type(self).__bool__(self)

def partition_suite(suite, classes, bins, reverse=False):
    """
    Partitions a test suite by test type. Also prevents duplicated tests.

    classes is a sequence of types
    bins is a sequence of TestSuites, one more than classes
    reverse changes the ordering of tests within bins

    Tests of type classes[i] are added to bins[i],
    tests with no match found in classes are place in bins[-1]
    """
    suite_class = type(suite)
    if reverse:
        suite = reversed(tuple(suite))
    for test in suite:
        if isinstance(test, suite_class):
            partition_suite(test, classes, bins, reverse=reverse)
        else:
            for i in range(len(classes)):
                if isinstance(test, classes[i]):
                    bins[i].add(test)
                    break
            else:
                bins[-1].add(test)

def reorder_suite(suite, classes, reverse=False):
    """
    Reorders a test suite by test type.

    `classes` is a sequence of types

    All tests of type classes[0] are placed first, then tests of type
    classes[1], etc. Tests with no match in classes are placed last.

    If `reverse` is True, tests within classes are sorted in opposite order,
    but test classes are not reversed.
    """
    class_count = len(classes)
    suite_class = type(suite)
    bins = [OrderedSet() for i in range(class_count + 1)]
    partition_suite(suite, classes, bins, reverse=reverse)
    reordered_suite = suite_class()
    for i in range(class_count + 1):
        reordered_suite.addTests(bins[i])
    return reordered_suite

def is_discoverable(label):
    """
    Check if a test label points to a python package or file directory.

    Relative labels like "." and ".." are seen as directories.
    """
    try:
        mod = import_module(label)
    except (ImportError, TypeError):
        pass
    else:
        return hasattr(mod, '__path__')

    return os.path.isdir(os.path.abspath(label))


class DiscoverRunner(DjangoTestSuiteRunner):
    """
    A Django test runner that uses unittest2 test discovery.
    """

    test_suite = unittest.TestSuite
    test_runner = unittest.TextTestRunner
    test_loader = unittest.defaultTestLoader
    reorder_by = (TestCase, SimpleTestCase)

    def __init__(self, pattern=None, top_level=None, verbosity=1,
                 interactive=True, failfast=False, keepdb=False,
                 reverse=False, debug_sql=False, **kwargs):

        self.pattern = pattern
        self.top_level = top_level

        self.verbosity = verbosity
        self.interactive = interactive
        self.failfast = failfast
        self.keepdb = keepdb
        self.reverse = reverse
        self.debug_sql = debug_sql

    @classmethod
    def add_arguments(cls, parser):
        parser.add_argument('-t', '--top-level-directory',
            action='store', dest='top_level', default=None,
            help='Top level of project for unittest discovery.')
        parser.add_argument('-p', '--pattern', action='store', dest='pattern',
            default="test*.py",
            help='The test matching pattern. Defaults to test*.py.')
        parser.add_argument('-k', '--keepdb', action='store_true', dest='keepdb',
            default=False,
            help='Preserves the test DB between runs.')
        parser.add_argument('-r', '--reverse', action='store_true', dest='reverse',
            default=False,
            help='Reverses test cases order.')
        parser.add_argument('-d', '--debug-sql', action='store_true', dest='debug_sql',
            default=False,
            help='Prints logged SQL queries on failure.')

    def setup_test_environment(self, **kwargs):
        setup_test_environment()
        settings.DEBUG = False
        unittest.installHandler()

    def build_suite(self, test_labels=None, extra_tests=None, **kwargs):
        suite = self.test_suite()
        test_labels = test_labels or ['.']
        extra_tests = extra_tests or []

        discover_kwargs = {}
        if self.pattern is not None:
            discover_kwargs['pattern'] = self.pattern
        if self.top_level is not None:
            discover_kwargs['top_level_dir'] = self.top_level

        for label in test_labels:
            kwargs = discover_kwargs.copy()
            tests = None

            label_as_path = os.path.abspath(label)

            # if a module, or "module.ClassName[.method_name]", just run those
            if not os.path.exists(label_as_path):
                tests = self.test_loader.loadTestsFromName(label)
            elif os.path.isdir(label_as_path) and not self.top_level:
                # Try to be a bit smarter than unittest about finding the
                # default top-level for a given directory path, to avoid
                # breaking relative imports. (Unittest's default is to set
                # top-level equal to the path, which means relative imports
                # will result in "Attempted relative import in non-package.").

                # We'd be happy to skip this and require dotted module paths
                # (which don't cause this problem) instead of file paths (which
                # do), but in the case of a directory in the cwd, which would
                # be equally valid if considered as a top-level module or as a
                # directory path, unittest unfortunately prefers the latter.

                top_level = label_as_path
                while True:
                    init_py = os.path.join(top_level, '__init__.py')
                    if os.path.exists(init_py):
                        try_next = os.path.dirname(top_level)
                        if try_next == top_level:
                            # __init__.py all the way down? give up.
                            break
                        top_level = try_next
                        continue
                    break
                kwargs['top_level_dir'] = top_level

            if not (tests and tests.countTestCases()) and is_discoverable(label):
                # Try discovery if path is a package or directory
                tests = self.test_loader.discover(start_dir=label, **kwargs)

                # Make unittest forget the top-level dir it calculated from this
                # run, to support running tests from two different top-levels.
                self.test_loader._top_level_dir = None

            suite.addTests(tests)

        for test in extra_tests:
            suite.addTest(test)

        return reorder_suite(suite, self.reorder_by, self.reverse)

    def get_resultclass(self):
        return DebugSQLTextTestResult if self.debug_sql else None

    def run_suite(self, suite, **kwargs):
        resultclass = self.get_resultclass()
        return self.test_runner(
            verbosity=self.verbosity,
            failfast=self.failfast,
            resultclass=resultclass,
        ).run(suite)

    def teardown_test_environment(self, **kwargs):
        unittest.removeHandler()
        teardown_test_environment()

    def suite_result(self, suite, result, **kwargs):
        return len(result.failures) + len(result.errors)

    def run_tests(self, test_labels, extra_tests=None, **kwargs):
        """
        Run the unit tests for all the test labels in the provided list.

        Test labels should be dotted Python paths to test modules, test
        classes, or test methods.

        A list of 'extra' tests may also be provided; these tests
        will be added to the test suite.

        Returns the number of tests that failed.
        """
        self.setup_test_environment()
        suite = self.build_suite(test_labels, extra_tests)
        old_config = self.setup_databases()
        result = self.run_suite(suite)
        self.teardown_databases(old_config)
        self.teardown_test_environment()
        return self.suite_result(suite, result)

def dependency_ordered(test_databases, dependencies):
    """
    Reorder test_databases into an order that honors the dependencies
    described in TEST[DEPENDENCIES].
    """
    ordered_test_databases = []
    resolved_databases = set()

    # Maps db signature to dependencies of all it's aliases
    dependencies_map = {}

    # sanity check - no DB can depend on its own alias
    for sig, (_, aliases) in test_databases:
        all_deps = set()
        for alias in aliases:
            all_deps.update(dependencies.get(alias, []))
        if not all_deps.isdisjoint(aliases):
            raise ImproperlyConfigured(
                "Circular dependency: databases %r depend on each other, "
                "but are aliases." % aliases)
        dependencies_map[sig] = all_deps

    while test_databases:
        changed = False
        deferred = []

        # Try to find a DB that has all it's dependencies met
        for signature, (db_name, aliases) in test_databases:
            if dependencies_map[signature].issubset(resolved_databases):
                resolved_databases.update(aliases)
                ordered_test_databases.append((signature, (db_name, aliases)))
                changed = True
            else:
                deferred.append((signature, (db_name, aliases)))

        if not changed:
            raise ImproperlyConfigured(
                "Circular dependency in TEST[DEPENDENCIES]")
        test_databases = deferred
    return ordered_test_databases


class DebugSQLTextTestResult(unittest.TextTestResult):
    def __init__(self, stream, descriptions, verbosity):
        self.logger = logging.getLogger('django.db.backends')
        self.logger.setLevel(logging.DEBUG)
        super(DebugSQLTextTestResult, self).__init__(stream, descriptions, verbosity)

    def startTest(self, test):
        self.debug_sql_stream = StringIO()
        self.handler = logging.StreamHandler(self.debug_sql_stream)
        self.logger.addHandler(self.handler)
        super(DebugSQLTextTestResult, self).startTest(test)

    def stopTest(self, test):
        super(DebugSQLTextTestResult, self).stopTest(test)
        self.logger.removeHandler(self.handler)
        if self.showAll:
            self.debug_sql_stream.seek(0)
            self.stream.write(self.debug_sql_stream.read())
            self.stream.writeln(self.separator2)

    def addError(self, test, err):
        super(DebugSQLTextTestResult, self).addError(test, err)
        self.debug_sql_stream.seek(0)
        self.errors[-1] = self.errors[-1] + (self.debug_sql_stream.read(),)

    def addFailure(self, test, err):
        super(DebugSQLTextTestResult, self).addFailure(test, err)
        self.debug_sql_stream.seek(0)
        self.failures[-1] = self.failures[-1] + (self.debug_sql_stream.read(),)

    def printErrorList(self, flavour, errors):
        for test, err, sql_debug in errors:
            self.stream.writeln(self.separator1)
            self.stream.writeln("%s: %s" % (flavour, self.getDescription(test)))
            self.stream.writeln(self.separator2)
            self.stream.writeln("%s" % err)
            self.stream.writeln(self.separator2)
            self.stream.writeln("%s" % sql_debug)