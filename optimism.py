# -*- coding: utf-8 -*-
"""
A very simple testing library. Includes capabilities for mocking input and setting up checks
for the results and/or printed output of arbitrary expressions.

optimism.py

## Example usage

```py
from optimism import *

# Simple example function
def f(x, y):
    "Example function"
    return x + y + 1

# Simple test for that function
test = testFunction(f) # line 9
case = test.case(1, 2)
case.checkReturnValue(4) # line 11


# Function that prints multiple lines of printed output
def display(message):
    print("The message is:")
    print('-' + message + '-')

# One test case with two lines of printed output
test = testFunction(display) # line 20
case = test.case('hello')
case.checkPrintedLines('The message is:', '-hello-') # line 22


# A function that uses input
def askNameAge():
    name = input("What is your name? ")
    age = input("How old are you? ")
    return (name, age)

test = testFunction(askNameAge) # line 31
case = test.case()
case.provideInputs("Name", "thirty")
case.checkReturnValue(('Name', 'thirty')) # line 34
case.checkPrintedLines( # line 35
    'What is your name? Name',
    'How old are you? thirty' # line 37
)
```

If we were to run this example file, we should see the following printed
output:

```txt
✓ example.py:11
✓ example.py:22
✓ example.py:34
✓ example.py:35
```

If an expectation is not met, the printed output would look different.
For example, if our first expectation had been 3 instead of 4, we'd see:

```txt
✗ example.py:11
  Result:
    4
  was NOT equivalent to the expected value:
    3
  Called function 'f' with arguments:
    x = 1
    y = 2
```

Note that line numbers reported for function calls that span multiple
lines may be different between Python versions before 3.8 and versions
3.8+.

## Core functionality

The main functions you'll need are:

- `trace` works like `print`, but shows some extra information, and you
  can use it as part of a larger expression. Use this for figuring out
  what's going wrong when your tests don't pass.
- `expect` takes two arguments and prints a check-mark if they're
  equivalent or an x if not. If they aren't equivalent, it prints
  details about values that are part of the first expression. Use this
  for expectations-based debugging.
- `expectType` works like `expect`, but the second argument is a type,
  and it checks whether the value of the first argument is an instance
  of that type or not.
- `testFunction` establishes a test manager object, which can be used to
  create test cases. When you call `testFunction` you specify the
  function that you want to test. The `.case` method of the resulting
  `TestManager` object can be used to set up individual test cases.
- `testFile` establishes a test manager object just like `testFunction`,
  but for running an entire file instead of for calling a single
  function.
- `testBlock` establishes a test manager object just like `testFunction`,
  but for running a block of code (given as a string).
- The `TestManager.case` method establishes a test case by specifying
  what arguments are going to be used with the associated function. It
  returns a `TestCase` object that can be used to establish
  expectations. For test managers based on files or blocks, no arguments
  are needed.
- The `TestCase.checkReturnValue` and `TestCase.checkPrintedLines`,
  and/or `TestCase.checkCustom` can be used to run checks for the return
  value and/or printed output of a test case.
- Normally, output printed during tests is hidden, but `showPrintedLines`
  can be used to show the text that's being captured instead.
- `TestCase.provideInputs` sets up inputs for a test case, so that
  interactive code can be tested without pausing for real user input.
- `detailLevel` can be called to control the level of detail printed in
  the output. It affects all tracing, expectation, and testing output
  produced until it gets called again.
- `showSummary` can be used to summarize the number of checks which
  passed or failed.
- `colors` can be used to enable or disable color codes for printed text.
  Disable this if you're getting garbled printed output.

TODO: Workaround for tracing in interactive console?
TODO: Prevent crash if expr_src is unavailable when tracing...

## Changelog

- Version 2.0 introduced the `TestManager` and `TestCase` classes, and
  got rid of automatic tracking for test cases. The old test case
  functionality was moved over to the `expect` function. This helps make
  tests more stable and makes meta-reasoning easier.
- Version 2.2.0 changed the names of `checkResult` and `checkOutputLines`
  to `checkReturnValue` and checkPrintedLines`
- Version 2.3.0 adds `testFunctionMaybe` for skippable tests if the
  target function hasn't been defined yet.
- Version 2.4.0 adds a more object-oriented structure behind the scenes,
  without changing any core API functions. It also adds support for
  variable specifications in block tests.
"""

# TODO: Cache compiled ASTs!

__version__ = "2.5.0"

import sys
import traceback
import inspect
import ast
import copy
import io
import os
import re
import types
import builtins
import cmath
import textwrap


#---------#
# Globals #
#---------#

ALL_CASES = {}
"""
All test cases that have been created, organized by test-suite names. By
default all cases are added to the 'default' test suite, but this can be
changed using `startTestSuite`. Each entry has a test suite name as the
key and a list of `TestCase` objects as the value.
"""

_CURRENT_SUITE_NAME = "default"
"""
The name of the current test suite, which organizes newly-created test
cases within the ALL_CASES variable. Use `startTestSuite` to begin/resume
a new test suite, and `currentTestSuite` to retrieve the value.
"""

COMPLETED_PER_LINE = {}
"""
A dictionary mapping function names to dictionaries mapping (filename,
line-number) pairs to counts. Each count represents the number of
functions of that name which have finished execution on the given line
of the given file already. This allows us to figure out which expression
belongs to which invocation if `get_my_context` is called multiple times
from the same line of code.
"""

DETAIL_LEVEL = 0
"""
The current detail level, which controls how verbose our messages are.
See `detailLevel`.
"""

SKIP_ON_FAILURE = "case"
"""
Controls which checks get skipped when a check fails. If left at the
default value of `'case'`, subsequent checks for the same test case will
be skipped when one fails. If set to `'manager'`, then all checks for any
case from a case manager will be skipped when any check for any case
derived from that manager fails. Any other value will disable the
skipping of checks based on failures.
"""

COLORS = True
"""
Whether to print ANSI color control sequences to color the printed output
or not.
"""

MSG_COLORS = {
    "succeeded": "34", # blue
    "skipped": "33", # yellow
    "failed": "1;31", # bright red
    "reset": "0", # resets color properties
}

IGNORE_TRAILING_WHITESPACE = True
"""
Controls equality and inclusion tests on strings, including multiline
strings, causing them to ignore trailing whitespace. True by default,
since trailing whitespace is hard to reason about because it's
invisible.
"""

_SHOW_OUTPUT = False
"""
Controls whether or not output printed during tests appears as normal or
is suppressed. Control this using the `showPrintedLines` function.
"""

FLOAT_REL_TOLERANCE = 1e-8
"""
The relative tolerance for floating-point similarity (see
`cmath.isclose`).
"""

FLOAT_ABS_TOLERANCE = 1e-8
"""
The absolute tolerance for floating-point similarity (see
`cmath.isclose`).
"""


#--------#
# Errors #
#--------#

class TestError(Exception):
    """
    An error with the testing mechanisms, as opposed to an error with
    the actual code being tested.
    """
    pass


#-------------------#
# Test Case Classes #
#-------------------#

class NoResult:
    """
    A special class used to indicate the absence of a result when None
    is a valid result value.
    """
    pass


class TestCase:
    """
    Represents a specific test to run, managing things like specific
    arguments, inputs or available variables that need to be in place.
    Derived from a `TestManager` using the `TestManager.case` method.

    `TestCase` is abstract; subclasses should override a least the `run`
    and `testDetails` functions.
    """
    def __init__(self, manager):
        """
        A manager must be specified, but that's it. This does extra
        things like registering the case in the current test suite (see
        `startTestSuite`) and figuring out the location tag for the
        case.
        """
        self.manager = manager

        # Inputs to provide on stdin
        self.inputs = None

        # Results of running this case
        self.results = None

        # Whether to echo captured printed outputs (overrides global)
        self.echo = None

        # Location and tag for test case creation
        self.location = get_my_location()
        self.tag = tag_for(self.location)

        # List of outcomes of checks that were made. Each is a triple
        # with a True/False indicator for success/failure, a string tag
        # for the expectation, and a full result message.
        self.outcomes = []

        # Whether or not a check has failed for this case yet.
        self.any_failed = False

        # Register as a test case
        ALL_CASES.setdefault(_CURRENT_SUITE_NAME, []).append(self)

    def provideInputs(self, *inputLines):
        """
        Sets up fake inputs (each argument must be a string and is used
        for one line of input) for this test case. When information is
        read from stdin during the test, including via the `input`
        function, these values are the result. If you don't call
        `provideInputs`, then the test will pause and wait for real user
        input when `input` is called.

        You must call this before the test actually runs (i.e., before
        `TestCase.run` or one of the `check` functions is called),
        otherwise you'll get an error.
        """
        if self.results is not None:
            raise TestError(
                "You cannot provide inputs because this test case has"
                " already been run."
            )
        self.inputs = inputLines

    def showPrintedLines(self, show=True):
        """
        Overrides the global `showPrintedLines` setting for this test.
        Use None as the parameter to remove the override.
        """
        self.echo = show

    def _run(self, payload):
        """
        Given a payload (a zero-argument function), runs the payload
        while managing things like output capturing and input mocking.
        Sets the `self.results` field to reflect the results of the run,
        which will be a dictionary that has the following slots:

        - "result": The result value from a function call. This key
            will not be present for tests that don't have a result, like
            file or code block tests. To achieve this with a custom
            payload, have the payload return `NoResult`.
        - "output": The output printed during the test. Will be an empty
            string if nothing gets printed.
        - "error": An Exception object representing an error that
            occurred during the test, or None if no errors happened.
        - "traceback": If an exception occurred, this will be a string
            containing the traceback for that exception. Otherwise it
            will be None.

        In addition to being added to the results slot, this dictionary
        is also returned.
        """
        # Set up the `input` function to echo what is typed
        original_input = builtins.input

        def echoing_input(prompt):
            """
            A stand-in for the built-in input which echoes the received
            input to stdout, under the assumption that stdin will NOT be
            echoed to the output stream because the output stream is not
            the console any more.
            """
            nonlocal original_input
            result = original_input(prompt)
            sys.stdout.write(result + '\n')
            return result

        builtins.input = echoing_input

        # Set up a capturing stream for output
        outputCapture = CapturingStream()
        outputCapture.install()
        if self.echo or (self.echo is None and _SHOW_OUTPUT):
            outputCapture.echo()

        # Set up fake input contents
        if self.inputs is not None:
            fakeInput = io.StringIO('\n'.join(self.inputs))
            original_stdin = sys.stdin
            sys.stdin = fakeInput

        # Set up default values before we run things
        error = None
        tb = None
        value = NoResult

        # Actually run the test
        try:
            value = payload()
        except Exception as e:
            # Catch any error that occurred
            error = e
            tb = traceback.format_exc()
        finally:
            # Release stream captures and reset the input function
            outputCapture.uninstall()
            builtins.input = original_input
            if self.inputs is not None:
                sys.stdin = original_stdin

        # Grab captured output
        output = outputCapture.getvalue()

        # Create self.results w/ output, error, and maybe result value
        self.results = {
            "output": output,
            "error": error,
            "traceback": tb
        }
        if value is not NoResult:
            self.results["result"] = value

        # Return new results object
        return self.results

    def run(self):
        """
        Runs this test case, capturing printed output and supplying fake
        input if `TestCase.provideInputs` has been called. Stores the
        results in `self.results`. This will be called once
        automatically the first time an expectation method like
        `TestCase.checkReturnValue` is used, but the cached value will
        be re-used for subsequent expectations, unless you manually call
        this method again.

        This method is overridden by specific test case types.
        """
        raise NotImplementedError(
            "Cannot run a TestCase; you must create a specific kind of"
            " test case like a FunctionCase to be able to run it."
        )

    def fetchResults(self):
        """
        Fetches the results of the test, which will run the test if it
        hasn't already been run, but otherwise will just return the
        latest cached results.

        `run` describes the format of the results.
        """
        if self.results is None:
            self.run()
        return self.results

    def _create_success_message(
        self,
        tag,
        details,
        extra_details=None,
        include_test_details=True
    ):
        """
        Returns an expectation success message (a string) for an
        expectation with the given tag, using the given details and
        extra details. Unless `include_test_details` is set to False,
        details of the test expression/block will also be included (but
        only when the detail level is at least 1). The tag should be a
        filename:lineno string indicating where the expectation
        originated.
        """
        # Detail level 1 gives more output for successes
        if DETAIL_LEVEL < 1:
            result = f"✓ {tag}"
        else: # Detail level is at least 1
            result = (
                f"✓ expectation from {tag} met for test case at {self.tag}"
            )
            detail_msg = indent(details, 2)
            if not detail_msg.startswith('\n'):
                detail_msg = '\n' + detail_msg

            if DETAIL_LEVEL >= 2 and extra_details:
                extra_detail_msg = indent(extra_details, 2)
                if not extra_detail_msg.startswith('\n'):
                    extra_detail_msg = '\n' + extra_detail_msg

                detail_msg += extra_detail_msg

            # Test details unless suppressed
            if include_test_details:
                test_base, test_extra = self.testDetails()
                detail_msg += '\n' + indent(test_base, 2)
                if DETAIL_LEVEL >= 2 and test_extra is not None:
                    detail_msg += '\n' + indent(test_extra, 2)

            result += detail_msg

        return result

    def _create_failure_message(
        self,
        tag,
        details,
        extra_details=None,
        include_test_details=True
    ):
        """
        Creates a failure message string for an expectation with the
        given tag that includes the details and/or extra details
        depending on the current global detail level. Normally,
        information about the test that was run is included as well, but
        you can set `include_test_details` to False to prevent this.
        """
        # Detail level controls initial message
        if DETAIL_LEVEL < 1:
            result = f"✗ {tag}"
        else:
            result = (
                f"✗ expectation from {tag} NOT met for test case at"
                f" {self.tag}"
            )

        # Assemble our details message
        detail_msg = ''

        # Detail level controls printing of detail messages
        if DETAIL_LEVEL >= 0:
            detail_msg += '\n' + indent(details, 2)
        if DETAIL_LEVEL >= 1 and extra_details:
            detail_msg += '\n' + indent(extra_details, 2)

        # Test details unless suppressed
        if include_test_details:
            test_base, test_extra = self.testDetails()
            if DETAIL_LEVEL >= 0:
                detail_msg += '\n' + indent(test_base, 2)
            if DETAIL_LEVEL >= 1 and test_extra is not None:
                detail_msg += '\n' + indent(test_extra, 2)

        return result + detail_msg

    def _print_skip_message(self, tag, reason):
        """
        Prints a standard message about the check being skipped, using
        the given tag and a reason (shown only if detail level is 1+).
        """
        # Detail level controls initial message
        if DETAIL_LEVEL < 1:
            msg = f"~ {tag} (skipped)"
        else:
            msg = (
                f"~ check at {tag} for test case at {self.tag} skipped"
                f" ({reason})"
            )
        print_message(msg, color=msg_color("skipped"))

    def testDetails(self):
        """
        Returns a pair of strings containing base and extra details
        describing what was tested by this test case. If the base
        details capture all available information, the extra details
        value will be None.

        This method is abstract and only sub-class implementations
        actually do anything.
        """
        raise NotImplementedError(
            "Cannot get test details for a TestCase; you must create a"
            " specific kind of test case like a FunctionCase to be able"
            " to get test details."
        )

    def _should_skip(self):
        """
        Returns True if this check should be skipped based on a previous
        failure.
        """
        return (
            (SKIP_ON_FAILURE == "case" and self.any_failed)
         or (SKIP_ON_FAILURE == "manager" and self.manager.any_failed)
        )

    def _register_outcome(self, passed, tag, message):
        """
        Registers an outcome for this test case. `passed` should be
        either True or False indicating whether the check passed, `tag`
        is a string to label the outcome with, and `message` is the
        message displayed by the check. This appends an entry to
        `self.outcomes` with the passed boolean, the tag, and the message
        in a tuple, and it sets `self.any_failed` and
        `self.manager.any_failed` if the outcome is a failure.
        """
        self.outcomes.append((passed, tag, message))
        if not passed:
            self.any_failed = True
            self.manager.any_failed = True

    def checkReturnValue(self, expectedValue):
        """
        Checks the result value for this test case, comparing it against
        the given expected value and printing a message about success or
        failure depending on whether they are considered equivalent by
        the `checkEquality` function.

        If this is the first check performed using this test case, the
        test case will run; otherwise a cached result will be used.

        This method returns True if the expectation is met and False if
        it is not, in addition to printing a message indicating
        success/failure and recording that message along with the status
        and tag in `self.outcomes`. If the check is skipped, it returns
        None and does not add an entry to `self.outcomes`.
        """
        results = self.fetchResults()

        # Figure out the tag for this expectation
        myloc = get_my_location()
        tag = tag_for(myloc)

        # Skip this check if the case has failed already
        if self._should_skip():
            self._print_skip_message(tag, "prior test failed")
            # Note that we don't add an outcome here, and we return None
            # instead of True or False
            return None

        # Figure out whether we've got an error or an actual result
        if results["error"] is not None:
            # An error during testing
            tb = results["traceback"]
            tblines = tb.splitlines()
            if len(tblines) < 12:
                base_msg = "Failed due to an error:\n" + indent(tb, 2)
                extra_msg = None
            else:
                short_tb = '\n'.join(tblines[:4] + '...' + tblines[-4:])
                base_msg = "Failed due to an error:\n" + indent(short_tb, 2)
                extra_msg = "Full traceback is:\n" + indent(tb, 2)

            msg = self._create_failure_message(
                tag,
                base_msg,
                extra_msg
            )
            print_message(msg, color=msg_color("failed"))
            self._register_outcome(False, tag, msg)
            return False

        elif "result" not in results:
            # Likely impossible, since we verified the category above
            # and we're in a condition where no error was logged...
            msg = self._create_failure_message(
                tag,
                (
                    "This test case does not have a result value. (Did"
                    " you mean to use checkPrintedLines?)"
                )
            )
            print_message(msg, color=msg_color("failed"))
            self._register_outcome(False, tag, msg)
            return False

        else:
            # We produced a result, so check equality

            # Check equivalence
            passed = False
            if checkEquality(results["result"], expectedValue):
                equivalence = "equivalent to"
                passed = True
            else:
                equivalence = "NOT equivalent to"

            # Get short/long versions of result/expected
            short_result = ellipsis(repr(results["result"]), 72)
            full_result = repr(results["result"])
            short_expected = ellipsis(repr(expectedValue), 72)
            full_expected = repr(expectedValue)

            # Create base/extra messages
            if (
                short_result == full_result
            and short_expected == full_expected
            ):
                base_msg = (
                    f"Result:\n{indent(short_result, 2)}\nwas"
                    f" {equivalence} the expected value:\n"
                    f"{indent(short_expected, 2)}"
                )
                extra_msg = None
            else:
                base_msg = (
                    f"Result:\n{indent(short_result, 2)}\nwas"
                    f" {equivalence} the expected value:\n"
                    f"{indent(short_expected, 2)}"
                )
                extra_msg = ""
                if short_result != full_result:
                    extra_msg += (
                        f"Full result:\n{indent(full_result, 2)}\n"
                    )
                if short_expected != full_expected:
                    extra_msg += (
                        f"Full expected value:\n"
                        f"{indent(full_expected, 2)}\n"
                    )

            if passed:
                msg = self._create_success_message(
                    tag,
                    base_msg,
                    extra_msg
                )
                print_message(msg, color=msg_color("succeeded"))
                self._register_outcome(True, tag, msg)
                return True
            else:
                msg = self._create_failure_message(
                    tag,
                    base_msg,
                    extra_msg
                )
                print_message(msg, color=msg_color("failed"))
                self._register_outcome(False, tag, msg)
                return False

    def checkPrintedLines(self, *expectedLines):
        """
        Checks that the exact printed output captured during the test
        matches a sequence of strings each specifying one line of the
        output. Note that the global `IGNORE_TRAILING_WHITESPACE`
        affects how this function treats line matches.

        If this is the first check performed using this test case, the
        test case will run; otherwise a cached result will be used.

        This method returns True if the check succeeds and False if it
        fails, in addition to printing a message indicating
        success/failure and recording that message along with the status
        and tag in `self.outcomes`. If the check is skipped, it returns
        None and does not add an entry to `self.outcomes`.
        """
        # Fetch captured output
        results = self.fetchResults()
        output = results["output"]

        # Figure out the tag for this expectation
        myloc = get_my_location()
        tag = tag_for(myloc)

        # Skip this check if the case has failed already
        if self._should_skip():
            self._print_skip_message(tag, "prior test failed")
            # Note that we don't add an outcome here, and we return None
            # instead of True or False
            return None

        # Figure out whether we've got an error or an actual result
        if results["error"] is not None:
            # An error during testing
            tb = results["traceback"]
            tblines = tb.splitlines()
            if len(tblines) < 12:
                base_msg = "Failed due to an error:\n" + indent(tb, 2)
                extra_msg = None
            else:
                short_tb = '\n'.join(tblines[:4] + ['...'] + tblines[-4:])
                base_msg = "Failed due to an error:\n" + indent(short_tb, 2)
                extra_msg = "Full traceback is:\n" + indent(tb, 2)

            msg = self._create_failure_message(
                tag,
                base_msg,
                extra_msg
            )
            print_message(msg, color=msg_color("failed"))
            self._register_outcome(False, tag, msg)
            return False

        else:
            # We produced printed output, so check it

            # Get lines/single versions
            outLines = output.splitlines()
            expected = '\n'.join(expectedLines) + '\n'
            # TODO: What if the actual output doesn't end with '\n'?

            # Figure out equivalence category
            equivalence = None
            passed = False
            firstdiff = None
            if output == expected:
                equivalence = "exactly the same as"
                passed = True
            elif (
                len(outLines) == len(expectedLines)
            and all(
                    out.rstrip() == exp.rstrip()
                    for out, exp in zip(outLines, expectedLines)
                )
            ):
                if IGNORE_TRAILING_WHITESPACE:
                    equivalence = "equivalent to"
                    passed = True
                else:
                    equivalence = (
                        "equivalent (EXCEPT trailing whitespace) to"
                    )
            else:
                # Compute line lists w/out blank lines
                outNoBlanks = [line for line in outLines if line.strip()]
                expNoBlanks = [
                    line for line in expectedLines if line.strip()
                ]

                # Compute point of first difference
                i = None
                for i in range(min(len(outLines), len(expectedLines))):
                    if outLines[i].rstrip() != expectedLines[i].rstrip():
                        firstdiff = i + 1
                        break
                else:
                    if i is not None:
                        firstdiff = i + 2
                    else:
                        # Note: this is a line number, NOT a line index
                        firstdiff = 1

                # Check for blank/extra-only differences
                if all(
                    out.rstrip() == exp.rstrip()
                    for out, exp in zip(outNoBlanks, expNoBlanks)
                ):
                    if len(outNoBlanks) == len(expNoBlanks):
                        equivalence = "equivalent (EXCEPT blank lines) to"
                    elif len(outNoBlanks) < len(expNoBlanks):
                        equivalence = "missing some lines from"
                    else:
                        equivalence = "had extra lines compared to"
                # Check for case-only differences
                elif all(
                    out.rstrip().casefold() == exp.rstrip().casefold()
                    for out, exp in zip(outNoBlanks, expNoBlanks)
                ):
                    if len(outNoBlanks) == len(expNoBlanks):
                        equivalence = (
                            "equivalent (EXCEPT blank lines and/or case) to"
                        )
                    elif len(outNoBlanks) < len(expNoBlanks):
                        equivalence = "missing some lines from"
                    else:
                        equivalence = "had extra lines compared to"
                # Some other kind of difference
                else:
                    equivalence = "NOT the same as"

            # Get short/long representations of our strings
            short, long = dual_string_repr(output)
            short_exp, long_exp = dual_string_repr(expected)

            # Construct base and extra messages
            if short == long and short_exp == long_exp:
                base_msg = (
                    f"Printed lines:\n{indent(short, 2)}\nwere"
                    f" {equivalence} the expected printed"
                    f" lines:\n{indent(short_exp, 2)}"
                )
                extra_msg = None
            else:
                base_msg = (
                    f"Printed lines:\n{indent(short, 2)}\nwere"
                    f" {equivalence} the expected printed"
                    f" lines:\n{indent(short_exp, 2)}"
                )
                extra_msg = ""
                if short != long:
                    extra_msg += f"Full printed lines:\n{indent(long, 2)}\n"
                if short_exp != long_exp:
                    extra_msg += (
                        f"Full expected printed"
                        f" lines:\n{indent(long_exp, 2)}\n"
                    )

            # Add a message about where the first difference was found
            # for multi-line printed outputs
            if (
                firstdiff is not None
            and (len(expectedLines) > 1 or len(outLines) > 1)
            ):
                # Compute repr of the expected and actual lines that
                # differed, with allowance for past-end differences
                if len(outLines) >= firstdiff:
                    diffgot = repr(outLines[firstdiff - 1])
                else:
                    diffgot = "nothing (didn't print this many lines)"

                if len(expectedLines) >= firstdiff:
                    diffexp = repr(expectedLines[firstdiff - 1])
                else:
                    diffexp = "nothing (wasn't expecting this many lines)"

                # Add to our base message
                base_msg += (
                    f"\nFirst difference was found on line {firstdiff}"
                    f" where we expected:"
                    f'\n  {diffexp}\nbut we got:\n  {diffgot}'
                )

            if passed:
                msg = self._create_success_message(
                    tag,
                    base_msg,
                    extra_msg
                )
                print_message(msg, color=msg_color("succeeded"))
                self._register_outcome(True, tag, msg)
                return True
            else:
                msg = self._create_failure_message(
                    tag,
                    base_msg,
                    extra_msg
                )
                print_message(msg, color="1;31" if COLORS else None)
                self._register_outcome(False, tag, msg)
                return False

    def checkPrintedFragment(self, fragment, copies=1, allowExtra=False):
        """
        Works like checkPrintedLines, except instead of requiring that
        the printed output exactly match a set of lines, it requires that
        a certain fragment of text appears somewhere within the printed
        output (or perhaps that multiple non-overlapping copies appear,
        if the copies argument is set to a number higher than the
        default of 1).

        If allowExtra is set to True, more than the specified number of
        copies will be ignored, but by default, extra copies are not
        allowed.

        The fragment is matched against the entire output as a single
        string, so it may contain newlines and if it does these will
        only match newlines in the captured output. If
        `IGNORE_TRAILING_WHITESPACE` is active (it's on by default), the
        trailing whitespace in the output will be removed before
        matching, and trailing whitespace in the fragment will also be
        removed IF it has a newline after it (trailing whitespace at the
        end of the string with no final newline will be retained).

        This function returns True if the check succeeds and False if it
        fails, and prints a message either way. If the check is skipped,
        it returns None and does not add an entry to `self.outcomes`.
        """
        # Fetch captured output
        results = self.fetchResults()
        output = results["output"]

        # Figure out the tag for this expectation
        myloc = get_my_location()
        tag = tag_for(myloc)

        # Skip this check if the case has failed already
        if self._should_skip():
            self._print_skip_message(tag, "prior test failed")
            # Note that we don't add an outcome here, and we return None
            # instead of True or False
            return None

        # Figure out whether we've got an error or an actual result
        if results["error"] is not None:
            # An error during testing
            tb = results["traceback"]
            tblines = tb.splitlines()
            if len(tblines) < 12:
                base_msg = "Failed due to an error:\n" + indent(tb, 2)
                extra_msg = None
            else:
                short_tb = '\n'.join(tblines[:4] + '...' + tblines[-4:])
                base_msg = "Failed due to an error:\n" + indent(short_tb, 2)
                extra_msg = "Full traceback is:\n" + indent(tb, 2)

            msg = self._create_failure_message(
                tag,
                base_msg,
                extra_msg
            )
            print_message(msg, color=msg_color("failed"))
            self._register_outcome(False, tag, msg)
            return False

        else:
            # We produced printed output, so check it
            if IGNORE_TRAILING_WHITESPACE:
                matches = re.findall(
                    re.escape(trimWhitespace(fragment, True)),
                    trimWhitespace(output)
                )
            else:
                matches = re.findall(re.escape(fragment), output)
            passed = False
            if copies == 1:
                copiesPhrase = ""
                exactly = ""
                atLeast = "at least "
            else:
                copiesPhrase = f"{copies} copies of "
                exactly = "exactly "
                atLeast = "at least "

            fragShort, fragLong = dual_string_repr(fragment)
            outShort, outLong = dual_string_repr(output)

            if len(matches) == copies:
                passed = True
                base_msg = (
                    f"Found {exactly}{copiesPhrase}the target"
                    f" fragment in the printed output."
                    f"\nFragment was:\n{indent(fragShort, 2)}"
                    f"\nOutput was:\n{indent(outShort, 2)}"
                )
            elif allowExtra and len(matches) > copies:
                passed = True
                base_msg = (
                    f"Found {atLeast}{copiesPhrase}the target"
                    f" fragment in the printed output (found"
                    f" {len(matches)})."
                    f"\nFragment was:\n{indent(fragShort, 2)}"
                    f"\nOutput was:\n{indent(outShort, 2)}"
                )
            else:
                passed = False
                base_msg = (
                    f"Did not find {copiesPhrase}the target fragment"
                    f" in the printed output (found {len(matches)})."
                    f"\nFragment was:\n{indent(fragShort, 2)}"
                    f"\nOutput was:\n{indent(outShort, 2)}"
                )

            extra_msg = ""
            if fragLong != fragShort:
                extra_msg += f"Full fragment was:\n{indent(fragLong, 2)}"

            if outLong != outShort:
                if not extra_msg.endswith('\n'):
                    extra_msg += '\n'
                extra_msg += f"Full output was:\n{indent(outLong, 2)}"

            if passed:
                msg = self._create_success_message(
                    tag,
                    base_msg,
                    extra_msg
                )
                print_message(msg, color=msg_color("succeeded"))
                self._register_outcome(True, tag, msg)
                return True
            else:
                msg = self._create_failure_message(
                    tag,
                    base_msg,
                    extra_msg
                )
                print_message(msg, color="1;31" if COLORS else None)
                self._register_outcome(False, tag, msg)
                return False

    def checkCustom(self, checker):
        """
        Sets up a custom check using a testing function. The provided
        function will be given a dictionary as an argument, with the
        following keys:

        - "output": Output printed by the test case, as a string.
        - "result": the result value (for function tests only, otherwise
            this key will not be present).
        - "error": the error that occurred (or None if no error
            occurred).
        - "traceback": the traceback (a string, or None if there was no
            error).

        The testing function must return True to indicate success and
        False for failure. If it returns something other than True or
        False, it will be counted as a failure, and that value will be
        shown as part of the test result if the `DETAIL_LEVEL` is 1 or
        higher. If the check is skipped, it returns None and does not add
        an entry to `self.outcomes`.
        """
        results = self.fetchResults()
        test_result = checker(results)

        # Figure out the tag for this expectation
        myloc = get_my_location()
        tag = tag_for(myloc)

        # Skip this check if the case has failed already
        if self._should_skip():
            self._print_skip_message(tag, "prior test failed")
            # Note that we don't add an outcome here, and we return None
            # instead of True or False
            return None

        if test_result is True:
            msg = self._create_success_message(tag, "Custom check passed.")
            print_message(msg, color=msg_color("succeeded"))
            self._register_outcome(True, tag, msg)
            return True
        elif test_result is False:
            msg = self._create_failure_message(tag, "Custom check failed")
            print_message(msg, color="1;31" if COLORS else None)
            self._register_outcome(False, tag, msg)
            return False
        else:
            msg = self._create_failure_message(
                tag,
                "Custom check failed:\n" + indent(str(test_result), 2),
            )
            print_message(msg, color="1;31" if COLORS else None)
            self._register_outcome(False, tag, msg)
            return False


class FileCase(TestCase):
    """
    Runs a particular file when executed. Its manager should be a
    `FileManager`.
    """
    # __init__ is inherited

    def run(self):
        """
        Reads the target file, parses its code, and runs that code in an
        empty environment (except that `__name__` is set to
        `'__main__'`, to make the file behave as if it were run as the
        main file).
        """
        def payload():
            "Payload function to run a file."
            # Read the file
            with open(self.manager.target, 'r') as fin:
                src = fin.read()

            # Parse the file
            node = ast.parse(
                src,
                filename=self.manager.target,
                mode='exec'
            )

            # Compile the results
            code = compile(node, self.manager.target, 'exec')

            # Run the code, setting __name__ to __main__ (this is
            # why we don't just import the file)
            env = {"__name__": "__main__"}
            exec(code, env)

        return self._run(payload)

    def testDetails(self):
        """
        Returns a pair of strings containing base and extra details
        describing what was tested by this test case. If the base
        details capture all available information, the extra details
        value will be None.
        """
        return (
            f"Ran file '{self.manager.target}'",
            None # no further details to report
        )


class FunctionCase(TestCase):
    """
    Calls a particular function with specific arguments when run.
    """
    def __init__(self, manager, args=None, kwargs=None):
        """
        The arguments and/or keyword arguments to be used for the case
        are provided after the manager (as a list and a dictionary, NOT
        as actual arguments). If omitted, the function will be called
        with no arguments.
        """
        super().__init__(manager)
        self.args = args or ()
        self.kwargs = kwargs or {}

    def run(self):
        """
        Runs the target function with the arguments specified for this
        case. The 'result' slot of the `self.results` dictionary that it
        creates holds the return value of the function.
        """
        def payload():
            "Payload for running a function with specific arguments."
            return self.manager.target(*self.args, **self.kwargs)

        return self._run(payload)

    def testDetails(self):
        """
        Returns a pair of strings containing base and extra details
        describing what was tested by this test case. If the base
        details capture all available information, the extra details
        value will be None.
        """
        # Show function name + args, possibly with some abbreviation
        fn = self.manager.target
        msg = f"Called function '{fn.__name__}'"

        args = self.args if self.args is not None else []
        kwargs = self.kwargs if self.args is not None else {}
        all_args = len(args) + len(kwargs)

        argnames = fn.__code__.co_varnames[:all_args]
        if len(args) > len(argnames):
            msg += " with too many arguments (!):"
        elif all_args > 0:
            msg += " with arguments:"

        # TODO: Proper handling of *args and **kwargs entries!

        # Create lists of full and maybe-abbreviated argument
        # strings
        argstrings = []
        short_argstrings = []
        for i, arg in enumerate(args):
            if i < len(argnames):
                name = argnames[i]
            else:
                name = f"extra argument #{i - len(argnames) + 1}"
            short_name = ellipsis(name, 20)

            argstrings.append(f"{name} = {repr(arg)}")
            short_argstrings.append(
                f"{short_name} = {ellipsis(repr(arg), 60)}"
            )

        # Order kwargs by original kwargs order and then by natural
        # order of kwargs dictionary
        keyset = set(kwargs)
        ordered = list(filter(lambda x: x in keyset, argnames))
        rest = [k for k in kwargs if k not in ordered]
        for k in ordered + rest:
            argstrings.append(f"{k} = {repr(kwargs[k])}")
            short_name = ellipsis(k, 20)
            short_argstrings.append(
                f"{short_name} = {ellipsis(repr(kwargs[k]), 60)}"
            )

        full_args = '  ' + '\n  '.join(argstrings)
        # In case there are too many arguments
        if len(short_argstrings) < 20:
            short_args = '  ' + '\n  '.join(short_argstrings)
        else:
            short_args = (
                '  '
              + '\n  '.join(short_argstrings[:19])
              + f"...plus {len(argstrings) - 19} more arguments..."
            )

        if short_args == full_args:
            return (
                msg + '\n' + short_args,
                None
            )
        else:
            return (
                msg + '\n' + short_args,
                "Full arguments were:\n" + full_args
            )


class BlockCase(TestCase):
    """
    Executes a block of code (provided as text) when run. Per-case
    variables may be defined for the execution environment, which
    otherwise just has builtins.
    """
    def __init__(self, manager, assignments=None):
        """
        A dictionary of variable name : value assignments may be
        provided and these will be inserted into the execution
        environment for the code block. If omitted, no extra variables
        will be defined.
        """
        super().__init__(manager)
        self.assignments = assignments or {}

    def run(self):
        """
        Compiles and runs the target code block in an environment which
        is empty except for the assignments specified in this case (and
        builtins).
        """
        def payload():
            "Payload for running a code block specific variables active."
            env = dict(self.assignments)
            exec(self.manager.target, env)

        return self._run(payload)

    def testDetails(self):
        """
        Returns a pair of strings containing base and extra details
        describing what was tested by this test case. If the base
        details capture all available information, the extra details
        value will be None.
        """
        block = self.manager.target
        short = limited_repr(block)
        if block == short:
            # Short enough to show whole block
            return (
                "Ran code:\n" + indent(block, 2),
                None
            )

        else:
            # Too long to show whole block in short view...
            return (
                "Ran code:\n" + indent(short, 2),
                "Full code was:\n" + indent(block, 2)
            )


class SkipCase(TestCase):
    """
    A type of test case which actually doesn't run checks, but instead
    prints a message that the check was skipped.
    """
    # __init__ is inherited

    def run(self):
        """
        Since there is no real test, our results are fake. The keys
        "error" and "traceback" have None as their value, and "output"
        also has None. We add a key "skipped" with value True.
        """
        self.results = {
            "output": None,
            "error": None,
            "traceback": None,
            "skipped": True
        }
        return self.results

    def testDetails(self):
        """
        Provides a pair of topic/details strings about this test.
        """
        return (f"Skipped check of '{self.manager.target}'", None)

    def checkReturnValue(self, _, **__):
        """
        Skips the check.
        """
        self._print_skip_message(
            tag_for(get_my_location()),
            "testing target not available"
        )

    def checkPrintedLines(self, *_, **__):
        """
        Skips the check.
        """
        self._print_skip_message(
            tag_for(get_my_location()),
            "testing target not available"
        )

    def checkPrintedFragment(self, *_, **__):
        """
        Skips the check.
        """
        self._print_skip_message(
            tag_for(get_my_location()),
            "testing target not available"
        )

    def checkCustom(self, _, **__):
        """
        Skips the check.
        """
        self._print_skip_message(
            tag_for(get_my_location()),
            "testing target not available"
        )


#----------------------#
# Test Manager Classes #
#----------------------#

class TestManager:
    """
    Abstract base class for managing tests for a certain function, file,
    or block of code. Create these using the `testFunction`, `testFile`,
    and/or `testBlock` factory functions. The `TestManager.case`
    function can be used to derive `TestCase` objects which can then be
    used to set up checks.
    """
    case_type = TestCase
    """
    The case type determines what kind of test case will be constructed
    when calling the `TestManager.case` method. Subclasses override
    this.
    """

    def __init__(self, target):
        """
        A testing target (a filename string, function object, code
        string, or test label string) must be provided.
        """
        self.target = target
        # Keeps track of whether any cases derived from this manager have
        # failed so far
        self.any_failed = False

    def case(self):
        """
        Returns a `TestCase` object that will test the target
        file/function/block. Some manager types allow arguments to this
        function.
        """
        return self.case_type(self)


class FileManager(TestManager):
    """
    Manages test cases for running an entire file. Unlike other
    managers, cases for a file cannot have parameters. Calling
    `TestCase.provideInputs` on a case to provide inputs still means
    that having multiple cases can be useful, however.
    """
    case_type = FileCase

    def __init__(self, filename):
        """
        A FileManager needs a filename string that specifies which file
        we'll run when we run a test case.
        """
        if not isinstance(filename, str):
            raise TypeError(
                f"For a file test manager, the target must be a file"
                f" name string. (You provided a/an {type(filename)}.)"
            )
        super().__init__(filename)

    # case is inherited as-is


class FunctionManager(TestManager):
    """
    Manages test cases for running a specific function. Arguments to the
    `TestManager.case` function are passed to the function being tested
    for that case.
    """
    case_type = FunctionCase

    def __init__(self, function):
        """
        A FunctionManager needs a function object as the target. Each
        case will call that function with arguments provided when the
        case is created.
        """
        if not isinstance(function, types.FunctionType):
            raise TypeError(
                f"For a function test manager, the target must be a"
                f" function. (You provided a/an {type(function)}.)"
            )
        super().__init__(function)

    def case(self, *args, **kwargs):
        """
        Arguments supplied here are used when calling the function which
        is what happens when the case is run. Returns a `FunctionCase`
        object.
        """
        return self.case_type(self, args, kwargs)


class BlockManager(TestManager):
    """
    Manages test cases for running a block of code (from a string).
    Keyword arguments to the `TestManager.case` function are defined as
    variables before the block is executed in that case.
    """
    case_type = BlockCase

    def __init__(self, code):
        """
        A BlockManager needs a code string as the target.
        """
        if not isinstance(code, str):
            raise TypeError(
                f"For a 'block' test manager, the target must be a"
                f" string. (You provided a/an {type(code)}.)"
            )
        super().__init__(code)

    def case(self, **assignments):
        """
        Keyword argument supplied here will be defined as variables
        in the environment used to run the code block. Returns a
        `BlockCase` object.
        """
        return self.case_type(self, assignments)


class SkipManager(TestManager):
    """
    Manages fake test cases for a file, function, or code block that
    needs to be skipped (perhaps for a function that doesn't yet exist,
    for example). Cases derived are `SkipCase` objects which just print
    skip messages for any checks requested.
    """
    case_type = SkipCase

    def __init__(self, label):
        """
        Needs a label string to identify which tests are being skipped.
        """
        if not isinstance(label, str):
            raise TypeError(
                f"For a skip test manager, the target must be a string."
                f" (You provided a/an {type(label)}.)"
            )
        super().__init__(label)

    def case(self, *_, **__):
        """
        Accepts (and ignores) any extra arguments.
        """
        return super().case()


#----------------#
# Test factories #
#----------------#

def testFunction(fn):
    """
    Creates a test-manager for the given function.
    """
    if not isinstance(fn, types.FunctionType):
        raise TypeError(
            "Test target must be a function (use testFile or testBlock"
            " instead to test a file or block of code)."
        )

    return FunctionManager(fn)


def testFunctionMaybe(module, fname):
    """
    This function creates a test-manager for a named function from a
    specific module, but displays an alternate message and returns a
    dummy manager if that module doesn't define any variable with the
    target name. Useful for defining tests for functions that will be
    skipped if the functions aren't done yet.
    """
    # Message if we can't find the function
    if not hasattr(module, fname):
        print_message(
            f"Did not find '{fname}' in module '{module.__name__}'...",
            color=msg_color("skipped")
        )
        return SkipManager(f"{module.__name__}.{fname}")
    else:
        target = getattr(module, fname)
        if not isinstance(target, types.FunctionType):
            print_message(
                (
                    f"'{fname}' in module '{module.__name__}' is not a"
                    f" function..."
                ),
                color=msg_color("skipped")
            )
            return SkipManager(f"{module.__name__}.{fname}")
        else:
            return FunctionManager(target)


def testFile(filename):
    """
    Creates a test-manager for running the named file.
    """
    if not isinstance(filename, str):
        raise TypeError(
            "Test target must be a file name (use testFunction instead"
            " to test a function)."
        )

    if not os.path.exists(filename):
        raise FileNotFoundError(
            f"We cannot create a test for running '{filename}' because"
            f" that file does not exist."
        )

    return FileManager(filename)


def testBlock(code):
    """
    Creates a test-manager for running a block of code.
    """
    if not isinstance(code, str):
        raise TypeError(
            "Test target must be a code string (use testFunction instead"
            " to test a function)."
        )

    # TODO: This check is good, but avoiding multiple parsing passes
    # might be nice for larger code blocks...
    try:
        _ = ast.parse(code)
    except Exception:
        raise ValueError(
            "The code block you provided could not be parsed as Python"
            " code."
        )

    return BlockManager(code)


#----------------#
# Output capture #
#----------------#

class CapturingStream(io.StringIO):
    """
    An output capture object which is an `io.StringIO` underneath, but
    which has an option to also write incoming text to normal
    `sys.stdout`. Call the install function to begin capture.
    """
    def __init__(self, *args, **kwargs):
        """
        Passes arguments through to `io.StringIO`'s constructor.
        """
        self.original_stdout = None
        self.tee = False
        super().__init__(*args, **kwargs)

    def echo(self, doit=True):
        """
        Turn on echoing to stdout along with capture, or turn it off if
        False is given.
        """
        self.tee = doit

    def install(self):
        """
        Replaces `sys.stdout` to begin capturing printed output.
        Remembers the old `sys.stdout` value so that `uninstall` can
        work. Note that if someone else changes `sys.stdout` after this
        is installed, uninstall will set `sys.stdout` back to what it was
        when `install` was called, which could cause issues. For example,
        if we have two capturing streams A and B, and we call:

        ```py
        A.install()
        B.install()
        A.uninstall()
        B.uninstall()
        ```

        The original `sys.stdout` will not be restored. In general, you
        must uninstall capturing streams in the reverse order that you
        installed them.
        """
        self.original_stdout = sys.stdout
        sys.stdout = self

    def uninstall(self):
        """
        Returns `sys.stdout` to what it was before `install` was called,
        or does nothing if `install` was never called.
        """
        if self.original_stdout is not None:
            sys.stdout = self.original_stdout

    def reset(self):
        """
        Resets the captured output.
        """
        self.seek(0)
        self.truncate(0)

    def writelines(self, lines):
        """
        Override writelines to work through write.
        """
        for line in lines:
            self.write(line)

    def write(self, stuff):
        """
        Accepts a string and writes to our capture buffer (and to
        original stdout if `echo` has been called). Returns the number
        of characters written.
        """
        if self.tee and self.original_stdout is not None:
            self.original_stdout.write(stuff)
        super().write(stuff)


def showPrintedLines(show=True):
    """
    Changes the testing mechanisms so that printed output produced during
    tests is shown as normal in addition to being captured. Call it with
    False as an argument to disable this.
    """
    global _SHOW_OUTPUT
    _SHOW_OUTPUT = show


#---------------------#
# Debugging functions #
#---------------------#

def expect(expr, value):
    """
    Establishes an immediate expectation that the values of the two
    arguments should be equivalent. The expression provided will be
    picked out of the source code of the module calling `expect` (see
    `get_my_context`). The expression and sub-values will be displayed
    if the expectation is not met, and either way a message indicating
    success or failure will be printed. Use `detailLevel` to control how
    detailed the messages are.

    For `expect` to work properly, the following rules must be followed:

    1. When multiple calls to `expect` appear on a single line of the
        source code (something you should probably avoid anyway), none of
        the calls should execute more times than another when that line
        is executed (it's difficult to violate this, but examples
        include the use of `expect` multiple times on one line within
        generator or if/else expressions)
    2. None of the following components of the expression passed to
        `expect` should have side effects when evaluated:
        - Attribute accesses
        - Subscripts (including expressions inside brackets)
        - Variable lookups
        (Note that those things don't normally have side effects!)

    This function returns True if the expectation is met and False
    otherwise.
    """
    context = get_my_context(expect)
    tag = tag_for(context)

    short_result = ellipsis(repr(expr), 78)
    short_expected = ellipsis(repr(value), 78)
    full_result = repr(expr)
    full_expected = repr(value)

    if checkEquality(expr, value):
        message = f"✓ {tag}"
        equivalent = "equivalent to"
        msg_cat = "succeeded"
        same = True
    else:
        message = f"✗ {tag}"
        equivalent = "NOT equivalent to"
        msg_cat = "failed"
        same = False

    if DETAIL_LEVEL >= 1 or not same:
        message += f"""
  Result:
{indent(short_result, 4)}
  was {equivalent} the expected value:
{indent(short_expected, 4)}"""

    # Report full values if detail level is turned up and the short
    # values were abbreviations
    if DETAIL_LEVEL >= 1:
        if short_result != full_result:
            message += f"\n  Full result:\n{indent(full_result, 4)}"
        if short_expected != full_expected:
            message += (
                f"\n  Full expected value:\n{indent(full_expected, 4)}"
            )

    # Report info about the test expression
    base, extra = expr_details(context)
    if same and DETAIL_LEVEL >= 1 or not same and DETAIL_LEVEL >= 0:
        message += '\n' + indent(base, 2)

    if DETAIL_LEVEL >= 1 and extra:
        message += '\n' + indent(extra, 2)

    # Print our message and return our result
    print_message(message, color=msg_color(msg_cat))
    return same


def expectType(expr, typ):
    """
    Works like `expect`, but establishes an expectation for the type of
    the result of the expression, not for the exact value. The same
    rules must be followed as for `expect` for this to work properly.

    If the type of the expression's result is an instance of the target
    type, the expectation counts as met.
    """
    context = get_my_context(expectType)
    tag = tag_for(context)

    if type(expr) == typ:
        message = f"✓ {tag}"
        desc = "the expected type"
        msg_cat = "succeeded"
        same = True
    elif isinstance(expr, typ):
        message = f"✓ {tag}"
        desc = f"a kind of {typ}"
        msg_cat = "succeeded"
        same = True
    else:
        message = f"✗ {tag}"
        desc = f"NOT a kind of {typ}"
        msg_cat = "failed"
        same = False

    # Report on the type if the detail level warrants it
    if same and DETAIL_LEVEL >= 1 or not same and DETAIL_LEVEL >= 0:
        message += f"\n  The result type ({type(expr)}) was {desc}."

    # Report info about the test expression
    base, extra = expr_details(context)
    if same and DETAIL_LEVEL >= 1 or not same and DETAIL_LEVEL >= 0:
        message += '\n' + indent(base, 2)

    if DETAIL_LEVEL >= 1 and extra:
        message += '\n' + indent(extra, 2)

    # Print our message and return our result
    print_message(message, color=msg_color(msg_cat))
    return same


#------------------#
# Message Handling #
#------------------#

def indent(msg, level=2):
    """
    Indents every line of the given message (a string).
    """
    indent = ' ' * level
    return indent + ('\n' + indent).join(msg.splitlines())


def ellipsis(string, maxlen=40):
    """
    Returns the provided string as-is, or if it's longer than the given
    maximum length, returns the string, truncated, with '...' at the
    end, which will, including the ellipsis, be exactly the given
    maximum length. The maximum length must be 4 or more.
    """
    if len(string) > maxlen:
        return string[:maxlen - 3] + "..."
    else:
        return string


def dual_string_repr(string):
    """
    Returns a pair containing full and truncated representations of the
    given string. The formatting of even the full representation depends
    on whether it's a multi-line string or not and how long it is.
    """
    lines = string.splitlines()
    if len(repr(string)) < 80 and len(lines) == 1:
        full = repr(string)
        short = repr(string)
    else:
        full = '"""\\\n' + string + '"""'
        if len(string) < 240 and len(lines) <= 7:
            short = full
        elif len(lines) > 7:
            head = '\n'.join(lines[:7])
            short = '"""\\\n' + ellipsis(head, 240) + '"""'
        else:
            short = '"""\\\n' + ellipsis(string, 240) + '"""'

    return (full, short)


def limited_repr(string):
    """
    Given a string that might include multiple lines and/or lots of
    characters (regardless of lines), returns version cut off by
    ellipses either after 5 or so lines, or after 240 characters.
    Returns the full string if it's both less than 240 characters and
    less than 5 lines.
    """
    # Split by lines
    lines = string.splitlines()

    # Already short enough
    if len(string) < 240 and len(lines) < 5:
        return string

    # Try up to 5 lines, cutting them off until we've got a
    # short-enough head string
    for n in range(min(5, len(lines)), 0, -1):
        head = '\n'.join(lines[:n])
        if n < len(lines):
            head += '\n...'
        if len(head) < 240:
            break
    else:
        # If we didn't break, just use first 240 characters
        # of the string
        head = string[:240] + '...'

    # If we cut things too short (e.g., because of initial
    # empty lines) use first 240 characters of the string
    if len(head) < 12:
        head = string[:240] + '...'

    return head


def msg_color(category):
    """
    Returns an ANSI color code for the given category of message (one of
    "succeeded", "failed", "skipped", or "reset"), or returns None if
    COLORS is disabled or an invalid category is provided.
    """
    if not COLORS:
        return None
    else:
        return MSG_COLORS.get(category)


def print_message(msg, color=None):
    """
    Prints a test result message to sys.stderr, but also flushes stdout
    and stderr both beforehand and afterwards to improve message
    ordering.

    If a color is given, it should be an ANSI terminal color code string
    (just the digits, for example '34' for blue or '1;31' for bright red).
    """
    sys.stdout.flush()
    sys.stderr.flush()

    # Make the whole message blue
    if color:
        print(f"\x1b[{color}m", end="", file=sys.stderr)
        suffix = "\x1b[0m"
    else:
        suffix = ""

    print(msg + suffix, file=sys.stderr)

    sys.stdout.flush()
    sys.stderr.flush()


def expr_details(context):
    """
    Returns a pair of strings containing base and extra details for an
    expression as represented by a dictionary returned from
    `get_my_context`. The extra message may be an empty string if the
    base message contains all relevant information.
    """
    # Expression that was evaluated
    expr = context.get("expr_src", "???")
    short_expr = ellipsis(expr, 78)
    # Results
    msg = ""
    extra_msg = ""

    # Base message
    msg += f"Test expression was:\n{indent(short_expr, 2)}"

    # Figure out values to display
    vdict = context.get("values", {})
    if context.get("relevant") is not None:
        show = sorted(
            context["relevant"],
            key=lambda fragment: (expr.index(fragment), len(fragment))
        )
    else:
        show = sorted(
            vdict.keys(),
            key=lambda fragment: (expr.index(fragment), len(fragment))
        )

    if len(show) > 0:
        msg += "\nValues were:"

    longs = []
    for key in show:
        if key in vdict:
            val = repr(vdict[key])
        else:
            val = "???"

        entry = f"  {key} = {val}"
        fits = ellipsis(entry)
        msg += '\n' + fits
        if fits != entry:
            longs.append(entry)

    # Extra message
    if short_expr != expr:
        if extra_msg != "" and not extra_msg.endswith('\n'):
            extra_msg += '\n'
        extra_msg += f"Full expression:\n{indent(expr, 2)}"
    extra_values = sorted(
        [
            key
            for key in vdict.keys()
            if key not in context.get("relevant", [])
        ],
        key=lambda fragment: (expr.index(fragment), len(fragment))
    )
    if context.get("relevant") is not None and extra_values:
        if extra_msg != "" and not extra_msg.endswith('\n'):
            extra_msg += '\n'
        extra_msg += "Extra values:"
        for ev in extra_values:
            if ev in vdict:
                val = repr(vdict[ev])
            else:
                val = "???"

            entry = f"  {ev} = {val}"
            fits = ellipsis(entry, 78)
            extra_msg += '\n' + fits
            if fits != entry:
                longs.append(entry)

    if longs:
        if extra_msg != "" and not extra_msg.endswith('\n'):
            extra_msg += '\n'
        extra_msg += "Full values:"
        for entry in longs:
            extra_msg += '\n' + entry

    return msg, extra_msg


#------------#
# Comparison #
#------------#

def checkEquality(val1, val2):
    """
    Returns True if val1 is 'equal' to val2, and False otherwise.
    If IGNORE_TRAILING_WHITESPACE is True, will ignore trailing
    whitespace in two strings when comparing them for equality.
    """
    if (not isinstance(val1, str)) or (not isinstance(val2, str)):
        return compare(val1, val2) # use regular equality test
    # For two strings, pay attention to IGNORE_TRAILING_WHITESPACE
    elif IGNORE_TRAILING_WHITESPACE:
        # remove trailing whitespace from both strings (on all lines)
        return compare(trimWhitespace(val1), trimWhitespace(val2))
    else:
        return compare(val1, val2) # use regular equality test


def checkContainment(val1, val2):
    """
    Returns True if val1 is 'contained in' to val2, and False otherwise.
    If IGNORE_TRAILING_WHITESPACE is True, will ignore trailing
    whitespace in two strings when comparing them for containment.
    """
    if (not isinstance(val1, str)) or (not isinstance(val2, str)):
        return val1 in val2 # use regular containment test
    # For two strings, pay attention to IGNORE_TRAILING_WHITESPACE
    elif IGNORE_TRAILING_WHITESPACE:
        # remove trailing whitespace from both strings (on all lines)
        return trimWhitespace(val1) in trimWhitespace(val2)
    else:
        return val1 in val2 # use regular containment test


def trimWhitespace(st, requireNewline=False):
    """
    Assume st a string. Use .rstrip() to remove trailing whitespace from
    each line. This has the side effect of replacing complex newlines
    with just '\\n'. If requireNewline is set to true, only whitespace
    that comes before a newline will be trimmed, and whitespace which
    occurs at the end of the string on the last line will be retained if
    there is no final newline.
    """
    if requireNewline:
        return re.sub('[ \t]*([\r\n])', r'\1', st)
    else:
        result = '\n'.join(line.rstrip() for line in st.splitlines())
        # Restore final newline if there was one.
        if st.endswith('\n'):
            result += '\n'
        return result


def compare(val, ref, comparing=None):
    """
    Compares two values, allowing a bit of difference in terms of
    floating point numbers, including numbers in complex structures.
    Returns True if the two arguments are equivalent and false if not.

    Works for recursive data structures.
    """
    if comparing is None:
        comparing = set()

    cmpkey = (id(val), id(ref))
    if cmpkey in comparing:
        # Either they differ somewhere else, or they're functionally
        # identical
        # TODO: Does this really ward off all infinite recursion on
        # finite structures?
        return True

    comparing.add(cmpkey)

    if val == ref:
        return True
    else: # let's hunt for differences
        if (
            isinstance(val, (int, float, complex))
        and isinstance(ref, (int, float, complex))
        ): # what if they're both numbers?
            return cmath.isclose(
                val,
                ref,
                rel_tol=FLOAT_REL_TOLERANCE,
                abs_tol=FLOAT_ABS_TOLERANCE
            )
        elif type(val) != type(ref): # different types; not both numbers
            return False
        elif isinstance(val, (list, tuple)): # both lists or tuples
            if len(val) != len(ref):
                return False
            else:
                return all(
                    compare(val[i], ref[i], comparing)
                    for i in range(len(val))
                )

        elif isinstance(val, (set)): # both sets
            if len(val) != len(ref):
                return False
            onlyVal = (val - ref)
            onlyRef = (ref - val)
            # TODO: Faster here, but still handle float imprecision?!?
            return compare(sorted(onlyVal), sorted(onlyRef), comparing)

        elif isinstance(val, dict): # both dicts
            if len(val) != len(ref):
                return False

            vkeys = set(val.keys())
            rkeys = set(val.keys())
            onlyVal = sorted(vkeys - rkeys)
            onlyRef = sorted(rkeys - vkeys)
            both = vkeys & rkeys

            for key_index in range(len(onlyVal)):
                vk = onlyVal[key_index]
                rk = onlyRef[key_index]
                if not compare(vk, rk, comparing):
                    return False

                if not compare(val[vk], ref[rk], comparing):
                    return False

            return all(
                compare(val[k], ref[k], comparing)
                for k in both
            )

        else: # not sure what kind of thing this is...
            return val == ref


#-----------------------#
# Configuration control #
#-----------------------#

def detailLevel(level):
    """
    Sets the level of detail for printed messages.
    The detail levels are:

    * -1: Super-minimal output, with no details beyond success/failure.
    * 0: Succinct messages indicating success/failure, with minimal
        details when failure occurs.
    * 1: More verbose success/failure messages, with details about
        successes and more details about failures.
    """
    global DETAIL_LEVEL
    DETAIL_LEVEL = level


def attendTrailingWhitespace(on=True):
    """
    Call this function to force `optimism` to pay attention to
    whitespace at the end of lines when checking expectations. By
    default, such whitespace is removed both from expected
    values/output fragments and from captured outputs/results before
    checking expectations. To turn that functionality on again, you
    can call this function with False as the argument.
    """
    global IGNORE_TRAILING_WHITESPACE
    IGNORE_TRAILING_WHITESPACE = not on


def skipChecksAfterFail(mode="case"):
    """
    The argument should be either 'case' (the default), 'manager', or
    None. In 'manager' mode, when one check fails, any other checks of
    cases derived from that manager, including the case where the check
    failed, will be skipped. In 'case' mode, once a check fails any
    further checks of the same case will be skipped, but checks of other
    cases derived from the same manager will not be. In None mode (or if
    any other value is provided) no checks will be skipped because of
    failed checks (but they might be skipped for other reasons).
    """
    global SKIP_ON_FAILURE
    SKIP_ON_FAILURE = mode


#---------------------------------#
# Summarization and Case Tracking #
#---------------------------------#

def showSummary(suiteName=None):
    """
    Shows a summary of the number of checks in the current test suite
    (see `currentTestSuite`) that have been met or not. You can also
    give an argument to specify the name of the test suite to summarize.
    Prints output to sys.stderr.
    """
    if suiteName is None:
        suiteName = currentTestSuite()

    if suiteName not in ALL_CASES:
        raise ValueError(f"Test suite '{suiteName}' does not exist.")

    # Flush stdout & stderr to improve ordering
    sys.stdout.flush()
    sys.stderr.flush()

    met = []
    unmet = []
    for case in ALL_CASES[suiteName]:
        for passed, tag, msg in case.outcomes:
            if passed:
                met.append(tag)
            else:
                unmet.append(tag)

    print('---', file=sys.stderr)

    if len(unmet) == 0:
        if len(met) == 0:
            print("No expectations were established.", file=sys.stderr)
        else:
            print(
                f"All {len(met)} expectation(s) were met.",
                file=sys.stderr
            )
    else:
        if len(met) == 0:
            print(
                f"None of the {len(unmet)} expectation(s) were met!",
                file=sys.stderr
            )
        else:
            print(
                (
                    f"{len(unmet)} of the {len(met) + len(unmet)}"
                    f" expectation(s) were NOT met:"
                ),
                file=sys.stderr
            )
        if COLORS: # bright red
            print("\x1b[1;31m", end="", file=sys.stderr)
        for tag in unmet:
            print(f"  ✗ {tag}", file=sys.stderr)
        if COLORS: # reset
            print("\x1b[0m", end="", file=sys.stderr)
    print('---', file=sys.stderr)

    # Flush stdout & stderr to improve ordering
    sys.stdout.flush()
    sys.stderr.flush()


def currentTestSuite():
    """
    Returns the name of the current test suite (a string).
    """
    return _CURRENT_SUITE_NAME


def startTestSuite(name):
    """
    Starts a new test suite with the given name, or resumes an old one.
    Any cases created subsequently will be registered to that suite.
    """
    global _CURRENT_SUITE_NAME
    if not isinstance(name, str):
        raise TypeError(
            f"The test suite name must be a string (got: '{repr(name)}'"
            f" which is a {type(name)})."
        )
    _CURRENT_SUITE_NAME = name


def resetTestSuite(suiteName=None):
    """
    Resets the cases recorded in the current test suite (or the named
    test suite if an argument is provided).
    """
    if suiteName is None:
        suiteName = currentTestSuite()

    ALL_CASES[suiteName] = []


def deleteAllTestSuites():
    """
    Deletes all test suites, removing all recorded test cases, and
    setting the current test suite name back to "default".
    """
    global ALL_CASES, _CURRENT_SUITE_NAME
    _CURRENT_SUITE_NAME = "default"
    ALL_CASES = {}


def listCasesInSuite(suiteName=None):
    """
    Returns a list of test cases (`TestCase` objects) in the current test
    suite (or the named suite if an argument is provided).
    """
    if suiteName is None:
        suiteName = currentTestSuite()

    if suiteName not in ALL_CASES:
        raise ValueError(f"Test suite '{suiteName}' does not exist.")

    return ALL_CASES[suiteName][:]


def listAllCases():
    """
    Returns a list of all registered test cases (`TestCase` objects) in
    any known test suite. Note that if `deleteAllTestSuites` has been
    called, this will not include any `TestCase` objects created before
    that point.
    """
    result = []
    for suiteName in ALL_CASES:
        result.extend(ALL_CASES[suiteName])

    return result


#---------------#
# Color control #
#---------------#

def colors(enable=False):
    """
    Enables or disables colors in printed output. If your output does not
    support ANSI color codes, the color output will show up as garbage
    and you can disable this.
    """
    global COLORS
    COLORS = enable


#---------#
# Tracing #
#---------#

def trace(expr):
    """
    Given an expression (actually, of course, just a value), returns the
    value it was given. But also prints a trace message indicating what
    the expression was, what value it had, and the line number of that
    line of code.

    The file name and overlength results are printed only when the
    `detailLevel` is set to 1 or higher.
    """
    # Flush stdout & stderr to improve ordering
    sys.stdout.flush()
    sys.stderr.flush()

    ctx = get_my_context(trace)
    rep = repr(expr)
    short = ellipsis(repr(expr))
    tag = "{line}".format(**ctx)
    if DETAIL_LEVEL >= 1:
        tag = "{file}:{line}".format(**ctx)
    print(
        f"{tag} {ctx['expr_src']} ⇒ {short}",
        file=sys.stderr
    )
    if DETAIL_LEVEL >= 1 and short != rep:
        print("  Full result is:\n    " + rep, file=sys.stderr)

    # Flush stdout & stderr to improve ordering
    sys.stdout.flush()
    sys.stderr.flush()

    return expr


#------------------------------#
# Reverse evaluation machinery #
#------------------------------#

def get_src_index(src, lineno, col_offset):
    """
    Turns a line number and column offset into an absolute index into
    the given source string, assuming length-1 newlines.
    """
    lines = src.splitlines()
    above = lines[:lineno - 1]
    return sum(len(line) for line in above) + len(above) + col_offset


def test_gsr():
    """Tests for get_src_index."""
    s = 'a\nb\nc'
    assert get_src_index(s, 1, 0) == 0
    assert get_src_index(s, 2, 0) == 2
    assert get_src_index(s, 3, 0) == 4
    assert s[get_src_index(s, 1, 0)] == 'a'
    assert s[get_src_index(s, 2, 0)] == 'b'
    assert s[get_src_index(s, 3, 0)] == 'c'


def find_identifier_end(code, start_index):
    """
    Given a code string and an index in that string which is the start
    of an identifier, returns the index of the end of that identifier.
    """
    at = start_index + 1
    while at < len(code):
        ch = code[at]
        if not ch.isalpha() and not ch.isdigit() and ch != '_':
            break
        at += 1
    return at - 1


def test_find_identifier_end():
    """Tests for find_identifier_end."""
    assert find_identifier_end("abc.xyz", 0) == 2
    assert find_identifier_end("abc.xyz", 1) == 2
    assert find_identifier_end("abc.xyz", 2) == 2
    assert find_identifier_end("abc.xyz", 4) == 6
    assert find_identifier_end("abc.xyz", 5) == 6
    assert find_identifier_end("abc.xyz", 6) == 6
    assert find_identifier_end("abc_xyz123", 0) == 9
    assert find_identifier_end("abc xyz123", 0) == 2
    assert find_identifier_end("abc xyz123", 4) == 9
    assert find_identifier_end("x", 0) == 0
    assert find_identifier_end("  x", 2) == 2
    assert find_identifier_end("  xyz1", 2) == 5
    s = "def abc(def):\n  print(xyz)\n"
    assert find_identifier_end(s, 0) == 2
    assert find_identifier_end(s, 4) == 6
    assert find_identifier_end(s, 8) == 10
    assert find_identifier_end(s, 16) == 20
    assert find_identifier_end(s, 22) == 24


def unquoted_enumerate(src, start_index):
    """
    A generator that yields index, character pairs from the given code
    string, skipping quotation marks and the strings that they delimit,
    including triple-quotes and respecting backslash-escapes within
    strings.
    """
    quote = None
    at = start_index

    while at < len(src):
        char = src[at]

        # skip escaped characters in quoted strings
        if quote and char == '\\':
            # (thank goodness I don't have to worry about r-strings)
            at += 2
            continue

        # handle quoted strings
        elif char == '"' or char == "'":
            if quote == char:
                quote = None # single end quote
                at += 1
                continue
            elif src[at:at + 3] in ('"""', "'''"):
                tq = src[at:at + 3]
                at += 3 # going to skip these no matter what
                if tq == quote or tq[0] == quote:
                    # Ending triple-quote, or matching triple-quote at
                    # end of single-quoted string = ending quote +
                    # empty string
                    quote = None
                    continue
                else:
                    if quote:
                        # triple quote of other kind inside single or
                        # triple quoted string
                        continue
                    else:
                        quote = tq
                        continue
            elif quote is None:
                # opening single quote
                quote = char
                at += 1
                continue
            else:
                # single quote inside other quotes
                at += 1
                continue

        # Non-quote characters in quoted strings
        elif quote:
            at += 1
            continue

        else:
            yield (at, char)
            at += 1
            continue


def test_unquoted_enumerate():
    """Tests for unquoted_enumerate."""
    uqe = unquoted_enumerate
    assert list(uqe("abc'123'", 0)) == list(zip(range(3), "abc"))
    assert list(uqe("'abc'123", 0)) == list(zip(range(5, 8), "123"))
    assert list(uqe("'abc'123''", 0)) == list(zip(range(5, 8), "123"))
    assert list(uqe("'abc'123''", 1)) == [(1, 'a'), (2, 'b'), (3, 'c')]
    mls = "'''\na\nb\nc'''\ndef"
    assert list(uqe(mls, 0)) == list(zip(range(12, 16), "\ndef"))
    tqs = '"""\'\'\'ab\'\'\'\'""" cd'
    assert list(uqe(tqs, 0)) == [(15, ' '), (16, 'c'), (17, 'd')]
    rqs = "a'b'''c\"\"\"'''\"d\"''''\"\"\"e'''\"\"\"f\"\"\"'''"
    print(f"X: '{rqs[23]}'", file=sys.stderr)
    assert list(uqe(rqs, 0)) == [(0, 'a'), (6, 'c'), (23, 'e')]
    assert list(uqe(rqs, 6)) == [(6, 'c'), (23, 'e')]
    bss = "a'\\'b\\''c"
    assert list(uqe(bss, 0)) == [(0, 'a'), (8, 'c')]
    mqs = "'\"a'b\""
    assert list(uqe(mqs, 0)) == [(4, 'b')]


def find_nth_attribute_period(code, start_index, n):
    """
    Given a string of Python code and a start index within that string,
    finds the nth period character (counting from first = zero) after
    that start point, but only considers periods which are used for
    attribute access, i.e., periods outside of quoted strings and which
    are not part of ellipses. Returns the index within the string of the
    period that it found. A period at the start index (if there is one)
    will be counted. Returns None if there are not enough periods in the
    code. If the start index is inside a quoted string, things will get
    weird, and the results will probably be wrong.
    """
    for (at, char) in unquoted_enumerate(code, start_index):
        if char == '.':
            if code[at - 1:at] == '.' or code[at + 1:at + 2] == '.':
                # part of an ellipsis, so ignore it
                continue
            else:
                n -= 1
                if n < 0:
                    break

    # Did we hit the end of the string before counting below 0?
    if n < 0:
        return at
    else:
        return None


def test_find_nth_attribute_period():
    """Tests for find_nth_attribute_period."""
    assert find_nth_attribute_period("a.b", 0, 0) == 1
    assert find_nth_attribute_period("a.b", 0, 1) is None
    assert find_nth_attribute_period("a.b", 0, 100) is None
    assert find_nth_attribute_period("a.b.c", 0, 1) == 3
    assert find_nth_attribute_period("a.b.cde.f", 0, 1) == 3
    assert find_nth_attribute_period("a.b.cde.f", 0, 2) == 7
    s = "a.b, c.d, 'e.f', g.h"
    assert find_nth_attribute_period(s, 0, 0) == 1
    assert find_nth_attribute_period(s, 0, 1) == 6
    assert find_nth_attribute_period(s, 0, 2) == 18
    assert find_nth_attribute_period(s, 0, 3) is None
    assert find_nth_attribute_period(s, 0, 3) is None
    assert find_nth_attribute_period(s, 1, 0) == 1
    assert find_nth_attribute_period(s, 2, 0) == 6
    assert find_nth_attribute_period(s, 6, 0) == 6
    assert find_nth_attribute_period(s, 7, 0) == 18
    assert find_nth_attribute_period(s, 15, 0) == 18


def find_closing_item(code, start_index, openclose='()'):
    """
    Given a string of Python code, a starting index where there's an
    open paren, bracket, etc., and a 2-character string containing the
    opening and closing delimiters of interest (parentheses by default),
    returns the index of the matching closing delimiter, or None if the
    opening delimiter is unclosed. Note that the given code must not
    contain syntax errors, or the behavior will be undefined.

    Does NOT work with quotation marks (single or double).
    """
    level = 1
    open_delim = openclose[0]
    close_delim = openclose[1]
    for at, char in unquoted_enumerate(code, start_index + 1):
        # Non-quoted open delimiters
        if char == open_delim:
            level += 1

        # Non-quoted close delimiters
        elif char == close_delim:
            level -= 1
            if level < 1:
                break

        # Everything else: ignore it

    if level == 0:
        return at
    else:
        return None


def test_find_closing_item():
    """Tests for find_closing_item."""
    assert find_closing_item('()', 0, '()') == 1
    assert find_closing_item('()', 0) == 1
    assert find_closing_item('(())', 0, '()') == 3
    assert find_closing_item('(())', 1, '()') == 2
    assert find_closing_item('((word))', 0, '()') == 7
    assert find_closing_item('((word))', 1, '()') == 6
    assert find_closing_item('(("(("))', 0, '()') == 7
    assert find_closing_item('(("(("))', 1, '()') == 6
    assert find_closing_item('(("))"))', 0, '()') == 7
    assert find_closing_item('(("))"))', 1, '()') == 6
    assert find_closing_item('(()())', 0, '()') == 5
    assert find_closing_item('(()())', 1, '()') == 2
    assert find_closing_item('(()())', 3, '()') == 4
    assert find_closing_item('(""")(\n""")', 0, '()') == 10
    assert find_closing_item("\"abc(\" + ('''def''')", 9, '()') == 19
    assert find_closing_item("\"abc(\" + ('''def''')", 0, '()') is None
    assert find_closing_item("\"abc(\" + ('''def''')", 4, '()') is None
    assert find_closing_item("(()", 0, '()') is None
    assert find_closing_item("(()", 1, '()') == 2
    assert find_closing_item("()(", 0, '()') == 1
    assert find_closing_item("()(", 2, '()') is None
    assert find_closing_item("[]", 0, '[]') == 1
    assert find_closing_item("[]", 0) is None
    assert find_closing_item("{}", 0, '{}') == 1
    assert find_closing_item("aabb", 0, 'ab') == 3


def find_unbracketed_comma(code, start_index):
    """
    Given a string of Python code and a starting index, finds the next
    comma at or after that index which isn't surrounded by brackets of
    any kind that start at or after that index and which isn't in a
    quoted string. Returns the index of the matching comma, or None if
    there is none. Stops and returns None if it finds an unmatched
    closing bracket. Note that the given code must not contain syntax
    errors, or the behavior will be undefined.
    """
    seeking = []
    delims = {
        '(': ')',
        '[': ']',
        '{': '}'
    }
    closing = delims.values()
    for at, char in unquoted_enumerate(code, start_index):
        # Non-quoted open delimiter
        if char in delims:
            seeking.append(delims[char])

        # Non-quoted matching close delimiter
        elif len(seeking) > 0 and char == seeking[-1]:
            seeking.pop()

        # Non-quoted non-matching close delimiter
        elif char in closing:
            return None

        # A non-quoted comma
        elif char == ',' and len(seeking) == 0:
            return at

        # Everything else: ignore it

    # Got to the end
    return None


def test_find_unbracketed_comma():
    """Tests for find_unbracketed_comma."""
    assert find_unbracketed_comma('()', 0) is None
    assert find_unbracketed_comma('(),', 0) == 2
    assert find_unbracketed_comma('((,),)', 0) is None
    assert find_unbracketed_comma('((,),),', 0) == 6
    assert find_unbracketed_comma('((,),),', 1) == 4
    assert find_unbracketed_comma(',,,', 1) == 1
    assert find_unbracketed_comma('",,",","', 0) == 4
    assert find_unbracketed_comma('"""\n,,\n""","""\n,,\n"""', 0) == 10
    assert find_unbracketed_comma('"""\n,,\n""","""\n,,\n"""', 4) == 4
    assert find_unbracketed_comma('"""\n,,\n"""+"""\n,,\n"""', 0) is None
    assert find_unbracketed_comma('\n\n,\n', 0) == 2


def get_expr_src(src, call_node):
    """
    Gets the string containing the source code for the expression passed
    as the first argument to a function call, given the string source of
    the file that defines the function and the AST node for the function
    call.
    """
    # Find the child node for the first (and only) argument
    arg_expr = call_node.args[0]

    # If get_source_segment is available, use that
    if hasattr(ast, "get_source_segment"):
        return textwrap.dedent(
            ast.get_source_segment(src, arg_expr)
        ).strip()
    else:
        # We're going to have to do this ourself: find the start of the
        # expression and state-machine to find a matching paren
        start = get_src_index(src, call_node.lineno, call_node.col_offset)
        open_paren = src.index('(', start)
        end = find_closing_item(src, open_paren, '()')
        # Note: can't be None because that would have been a SyntaxError
        first_comma = find_unbracketed_comma(src, open_paren + 1)
        # Could be None if it's a 1-argument function
        if first_comma is not None:
            end = min(end, first_comma)
        return textwrap.dedent(src[open_paren + 1:end]).strip()


def get_ref_src(src, node):
    """
    Gets the string containing the source code for a variable reference,
    attribute, or subscript.
    """
    # Use get_source_segment if it's available
    if hasattr(ast, "get_source_segment"):
        return ast.get_source_segment(src, node)
    else:
        # We're going to have to do this ourself: find the start of the
        # expression and state-machine to find its end
        start = get_src_index(src, node.lineno, node.col_offset)

        # Figure out the end point
        if isinstance(node, ast.Attribute):
            # Find sub-attributes so we can count syntactic periods to
            # figure out where the name part begins to get the span
            inner_period_count = 0
            for node in ast.walk(node):
                if isinstance(node, ast.Attribute):
                    inner_period_count += 1
            inner_period_count -= 1 # for the node itself
            dot = find_nth_attribute_period(src, start, inner_period_count)
            end = find_identifier_end(src, dot + 1)

        elif isinstance(node, ast.Name):
            # It's just an identifier so we can find the end
            end = find_identifier_end(src, start)

        elif isinstance(node, ast.Subscript):
            # Find start of sub-expression so we can find opening brace
            # and then match it to find the end
            inner = node.slice
            if isinstance(inner, ast.Slice):
                pass
            elif hasattr(ast, "Index") and isinstance(inner, ast.Index):
                # 3.7 Index has a "value"
                inner = inner.value
            elif hasattr(ast, "ExtSlice") and isinstance(inner, ast.ExtSlice):
                # 3.7 ExtSlice has "dims"
                inner = inner.dims[0]
            else:
                raise TypeError(
                    f"Unexpected subscript slice type {type(inner)} for"
                    f" node:\n{ast.dump(node)}"
                )
            sub_start = get_src_index(src, inner.lineno, inner.col_offset)
            end = find_closing_item(src, sub_start - 1, "[]")

        return src[start:end + 1]


def deepish_copy(obj, memo=None):
    """
    Returns the deepest possible copy of the given object, using
    copy.deepcopy wherever possible and making shallower copies
    elsewhere. Basically a middle-ground between copy.deepcopy and
    copy.copy.
    """
    if memo is None:
        memo = {}
    if id(obj) in memo:
        return memo[id(obj)]

    try:
        result = copy.deepcopy(obj) # not sure about memo dict compatibility
        memo[id(obj)] = result
        return result

    except Exception:
        if isinstance(obj, list):
            result = []
            memo[id(obj)] = result
            result.extend(deepish_copy(item, memo) for item in obj)
            return result
        elif isinstance(obj, tuple):
            # Note: no way to pre-populate the memo, but also no way to
            # construct an infinitely-recursive tuple without having
            # some mutable structure at some layer...
            result = (deepish_copy(item, memo) for item in obj)
            memo[id(obj)] = result
            return result
        elif isinstance(obj, dict):
            result = {}
            memo[id(obj)] = result
            result.update(
                {
                    deepish_copy(key, memo): deepish_copy(value, memo)
                    for key, value in obj.items()
                }
            )
            return result
        elif isinstance(obj, set):
            result = set()
            memo[id(obj)] = result
            result |= set(deepish_copy(item, memo) for item in obj)
            return result
        else:
            # Can't go deeper I guess
            try:
                result = copy.copy(obj)
                memo[id(obj)] = result
                return result
            except Exception:
                # Can't even copy (e.g., a module)
                result = obj
                memo[id(obj)] = result
                return result


def get_external_calling_frame():
    """
    Uses the inspect module to get a reference to the stack frame which
    called into the `optimism` module. Returns None if it can't find an
    appropriate call frame in the current stack.

    Remember to del the result after you're done with it, so that
    garbage doesn't pile up.
    """
    myname = __name__
    cf = inspect.currentframe()
    while (
        hasattr(cf, "f_back")
    and cf.f_globals.get("__name__") == myname
    ):
        cf = cf.f_back

    return cf


def get_module(stack_frame):
    """
    Given a stack frame, returns a reference to the module where the
    code from that frame was defined.

    Returns None if it can't figure that out.
    """
    other_name = stack_frame.f_globals.get("__name__", None)
    return sys.modules.get(other_name)


def get_filename(stack_frame, speculate_filename=True):
    """
    Given a stack frame, returns the filename of the file in which the
    code which created that stack frame was defined. Returns None if
    that information isn't available via a __file__ global, or if
    speculate_filename is True (the default), uses the value of the
    frame's f_code.co_filename, which may not always be a real file on
    disk, or which is weird circumstances could be the name of a file on
    disk which is *not* where the code came from.
    """
    filename = stack_frame.f_globals.get("__file__")
    if filename is None and speculate_filename:
        filename = stack_frame.f_code.co_filename
    return filename


def get_code_line(stack_frame):
    """
    Given a stack frame, returns
    """
    return stack_frame.f_lineno


def evaluate_in_context(node, stack_frame):
    """
    Given an AST node which is an expression, returns the value of that
    expression as evaluated in the context of the given stack frame.

    Shallow copies of the stack frame's locals and globals are made in
    an attempt to prevent the code being evaluated from having any
    impact on the stack frame's values, but of course there's still some
    possibility of side effects...
    """
    expr = ast.Expression(node)
    code = compile(
        expr,
        stack_frame.f_globals.get("__file__", "__unknown__"),
        'eval'
    )
    return eval(
        code,
        copy.copy(stack_frame.f_globals),
        copy.copy(stack_frame.f_locals)
    )


def walk_ast_in_order(node):
    """
    Yields all of the descendants of the given node (or list of nodes)
    in execution order. Note that this has its limits, for example, if
    we run it on the code:

    ```py
    x = [A for y in C if D]
    ```

    It will yield the nodes for C, then y, then D, then A, and finally
    x, but in actual execution the nodes for D and A may be executed
    multiple times before x is assigned.
    """
    if node is None:
        pass # empty iterator
    elif isinstance(node, (list, tuple)):
        for child in node:
            yield from walk_ast_in_order(child)
    else: # must be an ast.something
        # Note: the node itself will be yielded LAST
        if isinstance(node, (ast.Module, ast.Interactive, ast.Expression)):
            yield from walk_ast_in_order(node.body)
        elif (
            hasattr(ast, "FunctionType")
        and isinstance(node, ast.FunctionType)
        ):
            yield from walk_ast_in_order(node.argtypes)
            yield from walk_ast_in_order(node.returns)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield from walk_ast_in_order(node.args)
            yield from walk_ast_in_order(node.returns)
            yield from walk_ast_in_order(reversed(node.decorator_list))
            yield from walk_ast_in_order(node.body)
        elif isinstance(node, ast.ClassDef):
            yield from walk_ast_in_order(node.bases)
            yield from walk_ast_in_order(node.keywords)
            yield from walk_ast_in_order(reversed(node.decorator_list))
            yield from walk_ast_in_order(node.body)
        elif isinstance(node, ast.Return):
            yield from walk_ast_in_order(node.value)
        elif isinstance(node, ast.Delete):
            yield from walk_ast_in_order(node.targets)
        elif isinstance(node, ast.Assign):
            yield from walk_ast_in_order(node.value)
            yield from walk_ast_in_order(node.targets)
        elif isinstance(node, ast.AugAssign):
            yield from walk_ast_in_order(node.value)
            yield from walk_ast_in_order(node.target)
        elif isinstance(node, ast.AnnAssign):
            yield from walk_ast_in_order(node.value)
            yield from walk_ast_in_order(node.annotation)
            yield from walk_ast_in_order(node.target)
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            yield from walk_ast_in_order(node.iter)
            yield from walk_ast_in_order(node.target)
            yield from walk_ast_in_order(node.body)
            yield from walk_ast_in_order(node.orelse)
        elif isinstance(node, (ast.While, ast.If, ast.IfExp)):
            yield from walk_ast_in_order(node.test)
            yield from walk_ast_in_order(node.body)
            yield from walk_ast_in_order(node.orelse)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            yield from walk_ast_in_order(node.items)
            yield from walk_ast_in_order(node.items)
        elif isinstance(node, ast.Raise):
            yield from walk_ast_in_order(node.cause)
            yield from walk_ast_in_order(node.exc)
        elif isinstance(node, ast.Try):
            yield from walk_ast_in_order(node.body)
            yield from walk_ast_in_order(node.handlers)
            yield from walk_ast_in_order(node.orelse)
            yield from walk_ast_in_order(node.finalbody)
        elif isinstance(node, ast.Assert):
            yield from walk_ast_in_order(node.test)
            yield from walk_ast_in_order(node.msg)
        elif isinstance(node, ast.Expr):
            yield from walk_ast_in_order(node.value)
        # Import, ImportFrom, Global, Nonlocal, Pass, Break, and
        # Continue each have no executable content, so we'll yield them
        # but not any children

        elif isinstance(node, ast.BoolOp):
            yield from walk_ast_in_order(node.values)
        elif hasattr(ast, "NamedExpr") and isinstance(node, ast.NamedExpr):
            yield from walk_ast_in_order(node.value)
            yield from walk_ast_in_order(node.target)
        elif isinstance(node, ast.BinOp):
            yield from walk_ast_in_order(node.left)
            yield from walk_ast_in_order(node.right)
        elif isinstance(node, ast.UnaryOp):
            yield from walk_ast_in_order(node.operand)
        elif isinstance(node, ast.Lambda):
            yield from walk_ast_in_order(node.args)
            yield from walk_ast_in_order(node.body)
        elif isinstance(node, ast.Dict):
            for i in range(len(node.keys)):
                yield from walk_ast_in_order(node.keys[i])
                yield from walk_ast_in_order(node.values[i])
        elif isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            yield from walk_ast_in_order(node.elts)
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
            yield from walk_ast_in_order(node.generators)
            yield from walk_ast_in_order(node.elt)
        elif isinstance(node, ast.DictComp):
            yield from walk_ast_in_order(node.generators)
            yield from walk_ast_in_order(node.key)
            yield from walk_ast_in_order(node.value)
        elif isinstance(node, (ast.Await, ast.Yield, ast.YieldFrom)):
            yield from walk_ast_in_order(node.value)
        elif isinstance(node, ast.Compare):
            yield from walk_ast_in_order(node.left)
            yield from walk_ast_in_order(node.comparators)
        elif isinstance(node, ast.Call):
            yield from walk_ast_in_order(node.func)
            yield from walk_ast_in_order(node.args)
            yield from walk_ast_in_order(node.keywords)
        elif isinstance(node, ast.FormattedValue):
            yield from walk_ast_in_order(node.value)
            yield from walk_ast_in_order(node.format_spec)
        elif isinstance(node, ast.JoinedStr):
            yield from walk_ast_in_order(node.values)
        elif isinstance(node, (ast.Attribute, ast.Starred)):
            yield from walk_ast_in_order(node.value)
        elif isinstance(node, ast.Subscript):
            yield from walk_ast_in_order(node.value)
            yield from walk_ast_in_order(node.slice)
        elif isinstance(node, ast.Slice):
            yield from walk_ast_in_order(node.lower)
            yield from walk_ast_in_order(node.upper)
            yield from walk_ast_in_order(node.step)
        # Constant and Name nodes don't have executable contents

        elif isinstance(node, ast.comprehension):
            yield from walk_ast_in_order(node.iter)
            yield from walk_ast_in_order(node.ifs)
            yield from walk_ast_in_order(node.target)
        elif isinstance(node, ast.ExceptHandler):
            yield from walk_ast_in_order(node.type)
            yield from walk_ast_in_order(node.body)
        elif isinstance(node, ast.arguments):
            yield from walk_ast_in_order(node.defaults)
            yield from walk_ast_in_order(node.kw_defaults)
            if hasattr(node, "posonlyargs"):
                yield from walk_ast_in_order(node.posonlyargs)
            yield from walk_ast_in_order(node.args)
            yield from walk_ast_in_order(node.vararg)
            yield from walk_ast_in_order(node.kwonlyargs)
            yield from walk_ast_in_order(node.kwarg)
        elif isinstance(node, ast.arg):
            yield from walk_ast_in_order(node.annotation)
        elif isinstance(node, ast.keyword):
            yield from walk_ast_in_order(node.value)
        elif isinstance(node, ast.withitem):
            yield from walk_ast_in_order(node.context_expr)
            yield from walk_ast_in_order(node.optional_vars)
        # alias and typeignore have no executable members

        # Finally, yield this node itself
        yield node


def find_call_nodes_on_line(node, frame, function, lineno):
    """
    Given an AST node, a stack frame, a function object, and a line
    number, looks for all function calls which occur on the given line
    number and which are calls to the given function (as evaluated in
    the given stack frame).

    Note that calls to functions defined as part of the given AST cannot
    be found in this manner, because the objects being called are newly
    created and one could not possibly pass a reference to one of them
    into this function. For that reason, if the function argument is a
    string, any function call whose call part matches the given string
    will be matched. Normally only Name nodes can match this way, but if
    ast.unparse is available, the string will also attempt to match
    (exactly) against the unparsed call expression.

    Calls that start on the given line number will match, but if there
    are no such calls, then a call on a preceding line whose expression
    includes the target line will be looked for and may match.

    The return value will be a list of ast.Call nodes, and they will be
    ordered in the same order that those nodes would be executed when
    the line of code is executed.
    """
    def call_matches(call_node):
        """
        Locally-defined matching predicate.
        """
        nonlocal function
        call_expr = call_node.func
        return (
            (
                isinstance(function, str)
            and (
                    (
                        isinstance(call_expr, ast.Name)
                    and call_expr.id == function
                    )
                 or (
                        isinstance(call_expr, ast.Attribute)
                    and call_expr.attr == function
                    )
                 or (
                        hasattr(ast, "unparse")
                    and ast.unparse(call_expr) == function
                    )
                )
            )
         or (
                not isinstance(function, str)
            and evaluate_in_context(call_expr, frame) is function
            )
        )

    result = []
    all_on_line = []
    for child in walk_ast_in_order(node):
        # only consider call nodes on the target line
        if (
            hasattr(child, "lineno")
        and child.lineno == lineno
        ):
            all_on_line.append(child)
            if isinstance(child, ast.Call) and call_matches(child):
                result.append(child)

    # If we didn't find any candidates, look outwards from ast nodes on
    # the target line to find a Call that encompasses them...
    if len(result) == 0:
        for on_line in all_on_line:
            here = getattr(on_line, "parent", None)
            while (
                here is not None
            and not isinstance(
                    here,
                    # Call (what we're looking for) plus most nodes that
                    # indicate there couldn't be a call grandparent:
                    (
                        ast.Call,
                        ast.Module, ast.Interactive, ast.Expression,
                        ast.FunctionDef, ast.AsyncFunctionDef,
                        ast.ClassDef,
                        ast.Return,
                        ast.Delete,
                        ast.Assign, ast.AugAssign, ast.AnnAssign,
                        ast.For, ast.AsyncFor,
                        ast.While,
                        ast.If,
                        ast.With, ast.AsyncWith,
                        ast.Raise,
                        ast.Try,
                        ast.Assert,
                        ast.Assert,
                        ast.Assert,
                        ast.Assert,
                        ast.Assert,
                        ast.Assert,
                        ast.Assert,
                        ast.Assert,
                    )
                )
            ):
                here = getattr(here, "parent", None)

            # If we found a Call that includes the target line as one
            # of its children...
            if isinstance(here, ast.Call) and call_matches(here):
                result.append(here)

    return result


def assign_parents(root):
    """
    Given an AST node, assigns "parent" attributes to each sub-node
    indicating their parent AST node. Assigns None as the value of the
    parent attribute of the root node.
    """
    for node in ast.walk(root):
        for child in ast.iter_child_nodes(node):
            child.parent = node

    root.parent = None


def is_inside_call_func(node):
    """
    Given an AST node which has a parent attribute, traverses parents to
    see if this node is part of the func attribute of a Call node.
    """
    if not hasattr(node, "parent") or node.parent is None:
        return False
    if isinstance(node.parent, ast.Call) and node.parent.func is node:
        return True
    else:
        return is_inside_call_func(node.parent)


def tag_for(located):
    """
    Given a dictionary which has 'file' and 'line' slots, returns a
    string to be used as the tag for a test with 'filename:line' as the
    format. Unless the `DETAIL_LEVEL` is 2 or higher, the filename will
    be shown without the full path.
    """
    filename = located.get('file', '???')
    if DETAIL_LEVEL < 2:
        filename = os.path.basename(filename)
    line = located.get('line', '?')
    return f"{filename}:{line}"


def get_my_location(speculate_filename=True):
    """
    Fetches the filename and line number of the external module whose
    call into this module ended up invoking this function. Returns a
    dictionary with "file" and "line" keys.

    If speculate_filename is False, then the filename will be set to
    None in cases where a __file__ global cannot be found, instead of
    using f_code.co_filename as a backup. In some cases, this is useful
    because f_code.co_filename may not be a valid file.
    """
    frame = get_external_calling_frame()
    try:
        filename = get_filename(frame, speculate_filename)
        lineno = get_code_line(frame)
    finally:
        del frame

    return { "file": filename, "line": lineno }


def get_my_context(function_or_name):
    """
    Returns a dictionary indicating the context of a function call,
    assuming that this function is called from within a function with the
    given name (or from within the given function), and that that
    function is being called from within a different module. The result
    has the following keys:

    - file: The filename of the calling module
    - line: The line number on which the call to the function occurred
    - src: The source code string of the calling module
    - expr: An AST node storing the expression passed as the first
        argument to the function
    - expr_src: The source code string of the expression passed as the
        first argument to the function
    - values: A dictionary mapping source code fragments to their
        values, for each variable reference in the test expression. These
        are deepish copies of the values encountered.
    - relevant: A list of source code fragments which appear in the
        values dictionary which are judged to be most-relevant to the
        result of the test.

    Currently, the relevant list just lists any fragments which aren't
    found in the func slot of Call nodes, under the assumption that we
    don't care as much about the values of the functions we're calling.

    Prints a warning and returns a dictionary with just "file" and
    "line" entries if the other context info is unavailable.
    """
    if isinstance(function_or_name, types.FunctionType):
        function_name = function_or_name.__name__
    else:
        function_name = function_or_name

    frame = get_external_calling_frame()
    try:
        filename = get_filename(frame)
        lineno = get_code_line(frame)
        if filename is None:
            src = None
        else:
            try:
                with open(filename, 'r') as fin:
                    src = fin.read()
            except Exception:
                # We'll assume here that the source is something like an
                # interactive shell so we won't warn unless the detail
                # level is turned up.
                if DETAIL_LEVEL >= 2:
                    print(
                        "Warning: unable to get calling code's source.",
                        file=sys.stderr
                    )
                    print(
                        (
                            "Call is on line {} of module {} from file"
                            " '{}'"
                        ).format(
                            lineno,
                            frame.f_globals.get("__name__"),
                            filename
                        ),
                        file=sys.stderr
                    )
                src = None

        if src is None:
            return {
                "file": filename,
                "line": lineno
            }

        src_node = ast.parse(src, filename=filename, mode='exec')
        assign_parents(src_node)
        candidates = find_call_nodes_on_line(
            src_node,
            frame,
            function_or_name,
            lineno
        )

        # What if there are zero candidates?
        if len(candidates) == 0:
            print(
                f"Warning: unable to find call node for {function_name}"
                f" on line {lineno} of file {filename}.",
                file=sys.stderr
            )
            return {
                "file": filename,
                "line": lineno
            }

        # Figure out how many calls to get_my_context have happened
        # referencing this line before, so that we know which call on
        # this line we might be
        prev_this_line = COMPLETED_PER_LINE\
            .setdefault(function_name, {})\
            .setdefault((filename, lineno), 0)
        match = candidates[prev_this_line % len(candidates)]

        # Record this call so the next one will grab the subsequent
        # candidate
        COMPLETED_PER_LINE[function_name][(filename, lineno)] += 1

        arg_expr = match.args[0]

        # Add .parent attributes
        assign_parents(arg_expr)

        # Source code for the expression
        expr_src = get_expr_src(src, match)

        # Prepare our result dictionary
        result = {
            "file": filename,
            "line": lineno,
            "src": src,
            "expr": arg_expr,
            "expr_src": expr_src,
            "values": {},
            "relevant": set()
        }

        # Walk expression to find values for each variable
        for node in ast.walk(arg_expr):
            # If it's potentially a reference to a variable...
            if isinstance(
                node,
                (ast.Attribute, ast.Subscript, ast.Name)
            ):
                key = get_ref_src(src, node)
                if key not in result["values"]:
                    # Don't re-evaluate multiply-reference expressions
                    # Note: we assume they won't take on multiple
                    # values; if they did, even our first evaluation
                    # would probably be inaccurate.
                    val = deepish_copy(evaluate_in_context(node, frame))
                    result["values"][key] = val
                    if not is_inside_call_func(node):
                        result["relevant"].add(key)

        return result

    finally:
        del frame
