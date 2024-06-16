"""
Authors: Peter Mawhorter
Consulted:
Date: 2022-2-18
Purpose: Tests for wordGuesser task.
"""

import random

import optimism

import wordGuesser


# Tests for letterHints
testLH = optimism.testFunctionMaybe(wordGuesser, 'letterHints')
testLH.case('abc', 'abc').checkReturnValue('@@@')
testLH.case('abc', 'abd').checkReturnValue('@@-')
testLH.case('abc', 'zzz').checkReturnValue('---')
testLH.case('abc', 'cba').checkReturnValue('*@*')
testLH.case('abc', 'cab').checkReturnValue('***')
testLH.case('truism', 'tattle').checkReturnValue('@-**--')
testLH.case('truism', 'melody').checkReturnValue('*-----')
testLH.case('truism', 'misery').checkReturnValue('***-*-')
testLH.case('truism', 'trusty').checkReturnValue('@@@**-')
testLH.case('tattle', 'truism').checkReturnValue('@-----')
testLH.case('misery', 'truism').checkReturnValue('-*-***')
testLH.case('trusty', 'truism').checkReturnValue('@@@-*-')

# Tests for getGuess
testGG = optimism.testFunctionMaybe(wordGuesser, 'getGuess')
caseGG_5 = testGG.case(5)
caseGG_5.provideInputs("abcde")
caseGG_5.checkReturnValue("abcde")
caseGG_5.checkPrintedLines("Guess a word (5 letters): abcde")

caseGG_3 = testGG.case(3)
caseGG_3.provideInputs("abcd", "ab", "abc")
caseGG_3.checkReturnValue("abc")
caseGG_3.checkPrintedLines(
    "Guess a word (3 letters): abcd",
    "You must guess a word with 3 letters.",
    "Guess a word (3 letters): ab",
    "You must guess a word with 3 letters.",
    "Guess a word (3 letters): abc",
)

# Tests for playGame
introLines = wordGuesser.INTRO.splitlines() + ['']

testPG = optimism.testFunctionMaybe(wordGuesser, 'playGame')
casePG_hello = testPG.case('hello')
casePG_hello.provideInputs('hi', 'howdy', 'however', 'light', 'hello')
casePG_hello.checkPrintedLines(
    *(
        introLines + [
            "The word has 5 letters.",
            "Guess a word (5 letters): hi",
            "You must guess a word with 5 letters.",
            "Guess a word (5 letters): howdy",
            "@*---",
            "Guess a word (5 letters): however",
            "You must guess a word with 5 letters.",
            "Guess a word (5 letters): light",
            "*--*-",
            "Guess a word (5 letters): hello",
            "Congratulations! You guessed it, the word was: hello",
            "Great job! You guessed the word in just 3 tries."
        ]
    )
)

casePG_goodbye = testPG.case('goodbye')
casePG_goodbye.provideInputs(
    'abcdefg',
    'hijklmn',
    'opqrstu',
    'vwxyzee',
    'goodbye'
)
casePG_goodbye.checkPrintedLines(
    *(
        introLines + [
            "The word has 7 letters.",
            "Guess a word (7 letters): abcdefg",
            "-*-@*-*",
            "Guess a word (7 letters): hijklmn",
            "-------",
            "Guess a word (7 letters): opqrstu",
            "*------",
            "Guess a word (7 letters): vwxyzee",
            "---*-*@",
            "Guess a word (7 letters): goodbye",
            "Congratulations! You guessed it, the word was: goodbye",
            "Great job! You guessed the word in just 5 tries."
        ]
    )
)

casePG_hi = testPG.case('hi')
casePG_hi.provideInputs('hi')
casePG_hi.checkPrintedLines(
    *(
        introLines + [
            "The word has 2 letters.",
            "Guess a word (2 letters): hi",
            "Congratulations! You guessed it, the word was: hi",
            "Wow, you guessed it in one try!"
        ]
    )
)
