# -*- coding: utf-8 -*-
# Copyright (c) 2013-2014 Simon Jagoe
# All rights reserved.
#
# This software may be modified and distributed under the terms
# of the 3-clause BSD license.  See the LICENSE.txt file for details.
from __future__ import absolute_import, unicode_literals

import sys
import time

from haas.result import TestCompletionStatus, separator2
from .i_result_handler_plugin import IResultHandlerPlugin


def get_test_description(test, descriptions=True):
    doc_first_line = test.shortDescription()
    if descriptions and doc_first_line:
        return '\n'.join((str(test), doc_first_line))
    else:
        return str(test)


class _WritelnDecorator(object):
    """Used to decorate file-like objects with a handy 'writeln' method"""
    def __init__(self, stream):
        self.stream = stream

    def __getattr__(self, attr):
        if attr in ('stream', '__getstate__'):
            raise AttributeError(attr)
        return getattr(self.stream, attr)

    def writeln(self, arg=None):
        if arg:
            self.write(arg)
        self.write('\n')  # text-mode streams translate to \r\n if needed


class QuietTestResultHandler(IResultHandlerPlugin):
    separator1 = '=' * 70
    separator2 = separator2

    def __init__(self, test_count):
        self.enabled = True
        self.stream = _WritelnDecorator(sys.stderr)
        self._test_count = test_count
        self.tests_run = 0
        self.descriptions = True
        self.expectedFailures = expectedFailures = []
        self.unexpectedSuccesses = unexpectedSuccesses = []
        self.skipped = skipped = []
        self.failures = failures = []
        self.errors = errors = []
        self._collectors = {
            TestCompletionStatus.failure: failures,
            TestCompletionStatus.error: errors,
            TestCompletionStatus.unexpected_success: unexpectedSuccesses,
            TestCompletionStatus.expected_failure: expectedFailures,
            TestCompletionStatus.skipped: skipped,
        }
        self.start_time = None
        self.stop_time = None

    @classmethod
    def from_args(cls, args, name, dest_prefix, test_count):
        if args.verbosity == 0:
            return cls(test_count=test_count)

    @classmethod
    def add_parser_arguments(self, parser, name, option_prefix, dest_prefix):
        pass

    def get_test_description(self, test):
        return get_test_description(test, descriptions=self.descriptions)

    def start_test(self, test):
        self.tests_run += 1

    def stop_test(self, test):
        pass

    def start_test_run(self):
        self.start_time = time.time()

    def stop_test_run(self):
        self.stop_time = time.time()
        self.print_errors()
        self.print_summary()

    def print_errors(self):
        """Print all errors and failures to the console.

        """
        self.stream.writeln()
        self.print_error_list('ERROR', self.errors)
        self.print_error_list('FAIL', self.failures)

    def print_error_list(self, error_kind, errors):
        """Print the list of errors or failures.

        Parameters
        ----------
        error_kind : str
            ``'ERROR'`` or ``'FAIL'``
        errors : list
            List of :class:`~haas.result.TestResult`

        """
        for result in errors:
            self.stream.writeln(self.separator1)
            self.stream.writeln(
                '%s: %s' % (error_kind, self.get_test_description(
                    result.test)))
            self.stream.writeln(self.separator2)
            self.stream.writeln(result.exception)

    def print_summary(self):
        self.stream.writeln(self.separator2)
        time_taken = self.stop_time - self.start_time

        run = self.tests_run

        self.stream.writeln("Ran %d test%s in %.3fs" %
                            (run, run != 1 and "s" or "", time_taken))
        self.stream.writeln()

        selfs = map(len, (self.expectedFailures,
                          self.unexpectedSuccesses,
                          self.skipped))
        expectedFails, unexpectedSuccesses, skipped = selfs

        infos = []
        if not self.was_successful():
            self.stream.write("FAILED")
            failed, errored = len(self.failures), len(self.errors)
            if failed:
                infos.append("failures=%d" % failed)
            if errored:
                infos.append("errors=%d" % errored)
        else:
            self.stream.write("OK")
        if skipped:
            infos.append("skipped=%d" % skipped)
        if expectedFails:
            infos.append("expected failures=%d" % expectedFails)
        if unexpectedSuccesses:
            infos.append("unexpected successes=%d" % unexpectedSuccesses)
        if infos:
            self.stream.writeln(" (%s)" % (", ".join(infos),))
        else:
            self.stream.write("\n")

    def was_successful(self):
        return (len(self.errors) == 0 and
                len(self.failures) == 0 and
                len(self.unexpectedSuccesses) == 0)

    def __call__(self, result):
        collector = self._collectors.get(result.status)
        if collector is not None:
            collector.append(result)


class StandardTestResultHandler(QuietTestResultHandler):

    _result_formats = {
        TestCompletionStatus.success: '.',
        TestCompletionStatus.failure: 'F',
        TestCompletionStatus.error: 'E',
        TestCompletionStatus.unexpected_success: 'u',
        TestCompletionStatus.expected_failure: 'x',
        TestCompletionStatus.skipped: 's',
    }

    @classmethod
    def from_args(cls, args, name, dest_prefix, test_count):
        if args.verbosity == 1:
            return cls(test_count=test_count)

    def __call__(self, result):
        super(StandardTestResultHandler, self).__call__(result)
        self.stream.write(self._result_formats[result.status])
        self.stream.flush()


class VerboseTestResultHandler(StandardTestResultHandler):

    _result_formats = {
        TestCompletionStatus.success: 'ok',
        TestCompletionStatus.failure: 'FAIL',
        TestCompletionStatus.error: 'ERROR',
        TestCompletionStatus.unexpected_success: 'unexpected success',
        TestCompletionStatus.expected_failure: 'expected failure',
        TestCompletionStatus.skipped: 'skipped',
    }

    @classmethod
    def from_args(cls, args, name, dest_prefix, test_count):
        if args.verbosity == 2:
            return cls(test_count=test_count)

    def start_test(self, test):
        super(VerboseTestResultHandler, self).start_test(test)
        padding = len(str(self._test_count))
        prefix = '[{timestamp}] ({run: >{padding}d}/{total:d}) '.format(
            timestamp=time.ctime(),
            run=self.tests_run,
            padding=padding,
            total=self._test_count,
        )
        self.stream.write(prefix)
        description = self.get_test_description(test)
        self.stream.write(description)
        self.stream.write(' ... ')
        self.stream.flush()

    def __call__(self, result):
        super(VerboseTestResultHandler, self).__call__(result)
        if result.message is not None:
            self.stream.write(" '{0}'".format(result.message))
        self.stream.writeln()
        self.stream.flush()


class SlowTestsResultHandler(IResultHandlerPlugin):
    separator1 = '=' * 70
    separator2 = separator2

    OPTION_DEFAULT = object()

    def __init__(self, number_to_summarize):
        self.enabled = True
        self.stream = _WritelnDecorator(sys.stderr)
        self.descriptions = True
        self.number_to_summarize = number_to_summarize
        self._test_results = []

    @classmethod
    def from_args(cls, args, name, dest_prefix, test_count):
        if args.summarize_slow_tests is not cls.OPTION_DEFAULT:
            number_to_summarize = args.summarize_slow_tests or 10
            if number_to_summarize > 0:
                return cls(number_to_summarize)

    @classmethod
    def add_parser_arguments(cls, parser, name, option_prefix, dest_prefix):
        parser.add_argument('--summarize-slow-tests', action='store', type=int,
                            nargs='?', default=cls.OPTION_DEFAULT,
                            help='Show N slowest tests (default 10)')

    def start_test(self, test):
        pass

    def stop_test(self, test):
        pass

    def start_test_run(self):
        pass

    def stop_test_run(self):
        self.print_summary()

    def print_summary(self):
        tests_by_time = sorted(
            self._test_results,
            key=lambda item: item.duration,
            reverse=True,
        )

        self.stream.writeln()
        self.stream.writeln(self.separator2)

        template = '{0} {1}'

        for test_result in tests_by_time[:self.number_to_summarize]:
            description = get_test_description(
                test_result.test, descriptions=self.descriptions)
            line = template.format(str(test_result.duration), description)
            self.stream.writeln(line)
        self.stream.writeln()

    def __call__(self, result):
        self._test_results.append(result)
