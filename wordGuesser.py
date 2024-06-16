"""
Authors: Alyshba Ahmed
Consulted:
Date: 3.03.2023
Purpose: wordGuesser task: Allows user to guess words and reveals
  which letters are correct (or misplaced but present).
"""

import random # will be used to play a game with a random word

#---------------#
# Provided Text #
#---------------#

# This variable has the text you'll need to print out at the start of
# each game, so you don't have to type it all in yourself. It's put in
# all-caps to indicate that it's a global variable: any function can use
# it, but it cannot be modified inside a function.
INTRO = """\
Welcome to guess-that-word!
You will guess what the word could be and we will reveal which letters
of your guess are correct. If a letter is in the word but in a different
location, we'll let you know.

'@' means this letter is correct.
'*' means this letter is present in a different spot.
'-' means this letter is not present.

Use the hints to guess the word!
"""


#----------------------#
# Write your code here #
#----------------------#

def letterHints(hidden, guess):
    """
    Uses the user's guess to see how close it is to the hidden word.
    """
    newString = ''
    for i in range(len(guess)):
        if guess[i] == hidden[i]:
            newString += "@"
        elif guess[i] in hidden:
            newString += "*"
        else:
            newString += "-"
    return newString 
    
letterHints('truism', 'trusty')

def getGuess(num):
    """
    Prompts users to guess the word of a correct length.
    """
    var = input("Guess a word (" + str(num) + " letters): ")
    while len(var) != num:
        print("You must guess a word with " + str(num) + " letters.")
        var = input("Guess a word (" + str(num) + " letters): ")
    return var
    
def playGame(hidden):
    """
    Combines previous two functions to prompt users to guess the word!
    """
    tries = 0
    print("Welcome to guess-that-word!")
    print("You will guess what the word could be and we will reveal which letters")
    print("of your guess are correct. If a letter is in the word but in a different")
    print("location, we'll let you know.")
    print("")
    print("'@' means this letter is correct.")
    print("'*' means this letter is present in a different spot.")
    print("'-' means this letter is not present.")
    print("")
    print("Use the hints to guess the word!")
    print("")
    print("The word has " + str(len(hidden)) + " letters.")
    num = len(hidden)
    guess = getGuess(num)
    while guess != hidden:
        print(letterHints(hidden, guess))
        guess = getGuess(num)
        tries += 1
    tries += 1
    print('Congratulations! You guessed it, the word was: '+ hidden)
    if tries == 1:
        print('Wow, you guessed it in one try!')
    elif tries < 7:
        print('Great job! You guessed the word in just '+ str(tries) + ' tries.')
    else:
        print('You guessed the word in ' + str(tries) + ' tries.')

#--------------#
# Random Games #
#--------------#

# This variable holds a list of words that we will use to pick a random
# word to play the game with. The list is not very long, so we don't
# use it to validate guesses. The words are all between 4 and 7 letters
# long, and most of them are drawn from the index of our textbook, or
# otherwise relate to computer science concepts. There are three words
# that start with each letter of the alphabet, except for 'x', 'y', and
# 'z'.
WORDS = [
    "assign", "alias", "append", "branch", "binary", "boolean",
    "catch", "comment", "copy", "data", "debug", "declare",
    "element", "error", "empty", "file", "float", "format",
    "global", "game", "grid", "hash", "header", "heap",
    "input", "integer", "iterate", "join", "joule", "jump",
    "keyword", "kernel", "keys", "loop", "list", "local",
    "mutable", "method", "module", "none", "newline", "nested",
    "object", "open", "order", "python", "print", "pattern",
    "quote", "queue", "quine", "range", "return", "recurse",
    "syntax", "string", "shell", "test", "tuple", "turtle",
    "update", "unique", "user", "value", "void", "virtual",
    "while", "wave", "word", "xerox", "yield", "zero", "zombie"
]


# Note: This won't work until you've finished playGame.

def playRandomGame():
    """
    Works like playGame, except the word is chosen randomly from the
    WORDS list. Use this to play a game where you don't know the answer
    ahead of time.
    """
    playGame(random.choice(WORDS))
