# This is derived from the Pyste version of utils.py.
# See http://www.boost.org/ for more information.

from __future__ import generators
import string
import sys

#==============================================================================
# enumerate
#==============================================================================
def enumerate(seq):
    i = 0
    for x in seq:
        yield i, x
        i += 1  


#==============================================================================
# makeid
#==============================================================================
_valid_chars = string.ascii_letters + string.digits + '_'
_valid_chars = dict(zip(_valid_chars, _valid_chars))

def makeid(name):
    'Returns the name as a valid identifier'
    if type(name) != str:
        print type(name), name
    newname = []
    for char in name:
        if char not in _valid_chars:
            char = '_'
        newname.append(char)
    newname = ''.join(newname)
    # avoid duplications of '_' chars
    names = [x for x in newname.split('_') if x]
    return '_'.join(names)

#==============================================================================
# generateUniqueName
#==============================================================================
def generateUniqueName(declList):
    return [makeid(x.FullName()) for x in declList]

#==============================================================================
# getClassBridgeName
#==============================================================================
def getClassBridgeName(c):
    return makeid(c.FullName()) + '_bridge'

#==============================================================================
# operatorToString
#==============================================================================
def operatorToString(op, unary=True):
    if op == '+':
        return 'add'
    elif op == '-':
        if unary:
            return 'negate'
        else:
            return 'subtract'
    elif op == '!':
        return 'not'
    elif op == '~':
        return 'bit_invert'
    elif op == '++':
        return 'increment'
    elif op == '--':
        return 'decrement'
    elif op == '*':
        return 'multiply'
    elif op == '/':
        return 'divide'
    elif op == '%':
        return 'modulo'
    elif op == '%':
        return 'bitwise_and'
    elif op == '|':
        return 'bitwise_or'
    elif op == '^':
        return 'bitwise_xor'
    elif op == '<<':
        return 'left_shift'
    elif op == '>>':
        return 'right_shift'
    elif op == '!=':
        return 'not_equal'
    elif op == '>':
        return 'greater_than'
    elif op == '<':
        return 'less_than'
    elif op == '>=':
        return 'greater_than_or_equal'
    elif op == '<=':
        return 'less_than_or_equal'
    elif op == '==':
        return 'equal'

#==============================================================================
# remove_duplicated_lines
#==============================================================================
def remove_duplicated_lines(text):
    includes = text.splitlines()
    d = dict([(include, 0) for include in includes])
    return '\n'.join(d.keys())


#==============================================================================
# left_equals
#==============================================================================
def left_equals(s):
        s = '// %s ' % s
        return s + ('='*(80-len(s))) + '\n'  


#==============================================================================
# post_mortem    
#==============================================================================
def post_mortem():

    def info(type, value, tb):
       if hasattr(sys, 'ps1') or not sys.stderr.isatty():
          # we are in interactive mode or we don't have a tty-like
          # device, so we call the default hook
          sys.__excepthook__(type, value, tb)
       else:
          import traceback, pdb
          # we are NOT in interactive mode, print the exception...
          traceback.print_exception(type, value, tb)
          print
          # ...then start the debugger in post-mortem mode.
          pdb.pm()

    sys.excepthook = info 
