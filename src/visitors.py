# $Id: visitors.py,v 1.12 2003-11-12 23:46:01 patrick Exp $

import re
from declarations import Function

class DeclarationVisitor:
   def __init__(self):
      self.decl         = None
      self.name         = None
      self.generic_name = None
      self.usage        = None
      self.no_ns_name   = None
      self.problem_type = False

   def visit(self, decl):
      assert("Not implemented")

   def getRawName(self, namespace = True):
      '''
      Returns the raw, unprocessed name of a declaration.
      '''
      if namespace:
         return self.name
      else:
         return self.no_ns_name

   def getGenericName(self):
      '''
      Returns a "generic" name following the rules for identifier names in
      most, if not all, programming languages.
      '''
      return self.generic_name

   def getUsage(self):
      '''
      Returns the safe usage of a declaration.  The definition of "safe" is
      that various internal processing has been performed to make the
      declaration suitable for usage in various situations.
      '''
      return self.usage

   def _makeGenericName(self):
      return '_'.join(self.decl.getFullNameAbstract())

   def _makeGenericFuncName(self):
      base_name = self._makeGenericName()
      param_types = [x[0].getCleanName() for x in self.decl.parameters]
      return base_name + '__' +'_'.join(param_types)

   def _checkForProblemType(self):
      '''
      Template method used find and process "problem" types.
      '''
      assert(False)

   def _processProblemType(self, typeName):
      '''
      Template method.
      '''
      assert(False)

class CPlusPlusVisitor(DeclarationVisitor):
   '''
   Basic, general-purpose C++ visitor.
   '''
   def __init__(self):
      DeclarationVisitor.__init__(self)

   def visit(self, decl):
      self.decl         = decl
      self.problem_type = False
      self.name         = decl.FullName()

      if isinstance(decl, Function):
         self.generic_name = self._makeGenericFuncName()
      else:
         self.generic_name = self._makeGenericName()

      self.no_ns_name = '::'.join(decl.name)
      self.usage = self.name

      # Deal with types that need special handling.
      self._checkForProblemType()

   def _checkForProblemType(self):
      full_name = self.decl.getFullNameAbstract()
      for s in full_name:
         if s.find('basic_string') != -1:
            self._processProblemType(s)
            break

   def _processProblemType(self, typeName):
      if typeName.find('basic_string') != -1:
         const = ''
         if self.decl.const:
            const = 'const '
   
         self.usage = const + 'char*'
         self.problem_type = True
         self.decl.must_marshal = False

class CPlusPlusParamVisitor(CPlusPlusVisitor):
   '''
   C++ visitor for function/method parameters.  This will handle the details
   associated with parameter types when marshaling is in effect.
   '''
   def __init__(self):
      CPlusPlusVisitor.__init__(self)
      self.__initialize()
      self.__param_name      = ''
      self.__orig_param_name = ''

   def __initialize(self):
      self.__pre_marshal  = ''
      self.__post_marshal = ''
      self.__must_marshal = False

   def visit(self, decl):
      self.__initialize()
      CPlusPlusVisitor.visit(self, decl)

      # If the parameter is passed by reference, we need to translate that into
      # being passed as a pointer instead.
      if decl.suffix == '&':
         if not self.problem_type:
            self.usage = re.sub(r"&", "*", self.name)

            self.__must_marshal = True
            self.__pre_marshal  = '%s %s = *%s' % \
                                  (self.getRawName(), self.__param_name,
                                   self.__orig_param_name)
#            self.__post_marshal = '*%s = %s' % \
#                                  (self.__orig_param_name, self.__param_name)

   def _processProblemType(self, typeName):
      # Perform default problem type processing first.
      CPlusPlusVisitor._processProblemType(self, typeName)

      if self.decl.suffix == '&' and not self.decl.const:
         self.usage += '*'

      if typeName.find('basic_string') != -1:
         if self.decl.suffix == '&' and not self.decl.const:
            self.__must_marshal = True
            self.__pre_marshal  = 'std::string %s = *%s' % \
                                  (self.__param_name, self.__orig_param_name)
            self.__post_marshal = '*%s = strdup(%s.c_str())' % \
                                  (self.__orig_param_name, self.__param_name)

   def mustMarshal(self):
      return self.__must_marshal

   def getMarshalParamName(self):
      assert(self.mustMarshal())
      return self.__param_name

   def setParamName(self, paramName):
      self.__param_name = 'marshal_' + paramName
      self.__orig_param_name = paramName

   def getPreCallMarshal(self):
      assert(self.mustMarshal())
      return self.__pre_marshal

   def getPostCallMarshal(self):
      assert(self.mustMarshal())
      return self.__post_marshal

class CPlusPlusReturnVisitor(CPlusPlusVisitor):
   '''
   C++ visitor for return type declarations.
   '''
   def __init__(self):
      CPlusPlusVisitor.__init__(self)

   def visit(self, decl):
      CPlusPlusVisitor.visit(self, decl)
      if decl.must_marshal:
         if decl.suffix == '&':
            self.usage = re.sub(r"&", "*", self.name)
         else:
            self.usage += '*'
      # If we have a type that is being returned by reference but that does not
      # require marshaling, we'll just copy it.  Since the data has to cross
      # the language boundary, there is no point in trying to retain a
      # reference.
      elif decl.suffix == '&':
         self.usage = re.sub(r"(const|&)", "", self.name)

class CSharpVisitor(DeclarationVisitor):
   '''
   Basic, general-purpose C# visitor.
   '''
   
   fundamental_types = ['bool', 'byte', 'sbyte', 'char', 'short', 'ushort',
                        'int', 'uint', 'long', 'ulong', 'float', 'double']

   def __init__(self):
      DeclarationVisitor.__init__(self)

   def visit(self, decl):
      self.decl         = decl
      self.problem_type = False

      self.name = '.'.join(decl.getFullNameAbstract())

      if isinstance(decl, Function):
         self.generic_name = self._makeGenericFuncName()
      else:
         self.generic_name = self._makeGenericName()

      self.no_ns_name = '.'.join(decl.name)
      self.usage = self.name
      # Deal with types that need special handling.
      self._checkForProblemType()

   def _checkForProblemType(self):
      full_name = self.decl.getFullNameAbstract()

      # XXX: Figure out if there is a simpler way of dealing with unsigned
      # integers.  It depends largely on the order that the type information
      # is returned ("int unsigned" versus "unsigned int").
      for s in full_name:
         if s.find('basic_string') != -1:
            self.usage = 'String'
            self.problem_type = True
            self.decl.must_marshal = False
            break
         # Using long long probably indicates a desire for a 64-bit integer.
         elif s.find('long long') != -1:
            if s.find('unsigned') != -1:
               self.usage = 'ulong'
            else:
               self.usage = 'long'
            break
         # Assume that a long (not a long long) is supposed to be a 32-bit
         # integer.
         elif s.find('long') != -1 or s.find('int') != -1:
            if s.find('unsigned') != -1:
               self.usage = 'uint'
            else:
               self.usage = 'int'
            break
         elif s.find('short') != -1:
            if s.find('unsigned') != -1:
               self.usage = 'ushort'
         # Translate char, which is 1 byte in C/C++, into byte.
         elif s.find('char') != -1:
            if s.find('unsigned') != -1:
               self.usage = 'byte'
            else:
               self.usage = 'sbyte'
            break

   def _isFundamentalType(self, decl):
      return self.usage in self.fundamental_types

class CSharpPInvokeParamVisitor(CSharpVisitor):
   '''
   C# visitor for function/method parameters used in P/Invoke declarations.
   This will handle the details associated with parameter types when marshaling
   is in effect.
   '''
   def __init__(self):
      CSharpVisitor.__init__(self)
      self.__needs_unsafe = False

   def visit(self, decl):
      CSharpVisitor.visit(self, decl)

      if decl.suffix == '&' or decl.suffix == '*':
         if not self.problem_type:
            if self._isFundamentalType(decl):
               self.__needs_unsafe = True
               if self.usage.find("&") != -1:
                  self.usage = re.sub(r"&", "*", self.usage)
               else:
                  self.usage += '*'
            else:
               self.usage = 'IntPtr'

   def needsUnsafe(self):
      return self.__needs_unsafe

class CSharpParamVisitor(CSharpVisitor):
   '''
   C# visitor for function/method parameters.  This will handle the details
   associated with parameter types when marshaling is in effect.
   '''
   def __init__(self):
      CSharpVisitor.__init__(self)
      self.__initialize()
      self.__param_name      = ''
      self.__orig_param_name = ''

   def __initialize(self):
      self.__pre_marshal  = ''
      self.__post_marshal = ''
      self.__must_marshal = False
      self.__needs_unsafe = False

   def visit(self, decl):
      self.__initialize()
      CSharpVisitor.visit(self, decl)

      if decl.suffix == '&' or decl.suffix == '*':
         if not self.problem_type:
            if self._isFundamentalType(decl):
               self.usage = 'ref ' + re.sub(r"[&*]", "", self.usage)
               self.__must_marshal = True
               self.__needs_unsafe = True
               self.__param_name   = '&' + self.__orig_param_name
            else:
               self.__must_marshal = True
               self.__param_name = self.__orig_param_name + '.mRawObject'

   def mustMarshal(self):
      return self.__must_marshal

   def needsUnsafe(self):
      return self.__needs_unsafe

   def getMarshalParamName(self):
      assert(self.mustMarshal())
      return self.__param_name

   # XXX: This parameter name stuff sucks.
   def setParamName(self, paramName):
      self.__orig_param_name = paramName
      self.__param_name = 'marshal_' + paramName

   def getPreCallMarshal(self):
      assert(self.mustMarshal())
      return self.__pre_marshal

   def getPostCallMarshal(self):
      assert(self.mustMarshal())
      return self.__post_marshal

   def _processProblemType(self, typeName):
      # Perform default problem type processing first.
      CSharpVisitor._processProblemType(self, typeName)

class CSharpReturnVisitor(CSharpVisitor):
   '''
   C# visitor for return type declarations.  This will handle the details
   associated with return types when marshaling is in effect.
   '''
   def __init__(self):
      CSharpVisitor.__init__(self)

   def visit(self, decl):
      CSharpVisitor.visit(self, decl)
