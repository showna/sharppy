# $Id: visitors.py,v 1.23 2003-11-24 20:50:43 patrick Exp $

import re

UNKNOWN            = -1
STD_STRING         = 0
CHAR               = 1
UNSIGNED_CHAR      = 2
SHORT              = 3
UNSIGNED_SHORT     = 4
INT                = 5
UNSIGNED_INT       = 6
LONG               = 7
UNSIGNED_LONG      = 8
LONG_LONG          = 9
UNSIGNED_LONG_LONG = 10
SHARED_PTR         = 11

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

   fundamental_types = ['bool', 'char', 'unsigned char', 'short',
                        'unsigned short', 'short unsigned int', 'int',
                        'unsigned int', 'long', 'unsigned long',
                        'long long int', 'long long unsigned int', 'float',
                        'double']

   def __init__(self):
      DeclarationVisitor.__init__(self)

   def visit(self, decl):
      self.decl         = decl
      self.problem_type = False
      self.name         = decl.FullName()
      self.generic_name = decl.getGenericName()
      self.no_ns_name = '::'.join(decl.name)
      self.usage = self.name

      # Deal with types that need special handling.
      self._checkForProblemType()

   def _checkForProblemType(self):
      full_name = self.decl.getFullNameAbstract()
      if full_name[0] == 'std' and full_name[1].find('basic_string', 0) != -1:
         self._processProblemType(STD_STRING)

   def _processProblemType(self, typeID):
      if typeID == STD_STRING:
         const = ''
         if self.decl.const:
            const = 'const '
   
         self.usage = const + 'char*'
         self.problem_type = True
         self.decl.must_marshal = False

   def _isFundamentalType(self):
      # We can search for fundamental types using self.decl.name[0] because
      # their name will always occupy a list with exactly one element.
      # Furthermore, a user-defined namespace cannot have the same name as a
      # fundamental type because those types are reserved words.
      return self.decl.name[0] in self.fundamental_types

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
         if not self.problem_type and not self._isFundamentalType():
            self.usage = re.sub(r"&", "*", self.name)

            self.__must_marshal = True
            self.__pre_marshal  = '%s %s = *%s' % \
                                  (self.getRawName(), self.__param_name,
                                   self.__orig_param_name)
#            self.__post_marshal = '*%s = %s' % \
#                                  (self.__orig_param_name, self.__param_name)

   def _processProblemType(self, typeID):
      # Perform default problem type processing first.
      CPlusPlusVisitor._processProblemType(self, typeID)

      if self.decl.suffix == '&' and not self.decl.const:
         self.usage += '*'

      if typeID == STD_STRING:
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
      self.__initialize()
      self.__result_var      = 'result'
      self.__temp_result_var = 'temp_result'

   def __initialize(self):
      self.__pre_marshal  = []
      self.__post_marshal = []
      self.__call_marshal = ''
      self.__must_marshal = False

   def visit(self, decl):
      self.__initialize()
      CPlusPlusVisitor.visit(self, decl)

      if decl.must_marshal:
         self.__must_marshal = True
         if decl.suffix == '&':
            self.usage = re.sub(r"&", "*", self.name)
         else:
            self.usage += '*'
         self.__call_marshal = self.__result_var + ' = new ' + self.getRawName() + '(%s)'
         self.__pre_marshal = []
         self.__post_marshal = []
      # If we have a type that is being returned by reference but that does not
      # require marshaling, we'll just copy it.  Since the data has to cross
      # the language boundary, there is no point in trying to retain a
      # reference.
      elif decl.suffix == '&':
         self.usage = re.sub(r"(const|&)", "", self.name)

   def mustMarshal(self):
      return self.__must_marshal

   def getMethodCall(self, callString, indent):
      # Declare the variable that will be used to return the result of calling
      # the method.
      output = '%s%s %s;\n' % (indent, self.usage, self.__result_var)

      # If we have to marshal the returned data, do that now.  This involves
      # the use of a temporary variable.
      if self.mustMarshal():
         for line in self.__pre_marshal:
            output += indent + line + "\n"
         if self.__call_marshal:
            output += indent
            output += self.__call_marshal % callString
            output += ';\n'
         else:
            output += '%s%s = %s;\n' % (indent, self.__temp_result_var,
                                        callString)
         for line in self.__post_marshal:
            output += indent + line + "\n"
      # If no marshaling is required, just assign the result of calling the
      # method to the return storage variable.
      else:
         output += '%s%s = %s;\n' % (indent, self.__result_var, callString)
      return output

   def getResultVarName(self):
      return self.__result_var

   def _processProblemType(self, typeID):
      # Perform default problem type processing first.
      CPlusPlusVisitor._processProblemType(self, typeID)

      if typeID == STD_STRING:
#         if self.usage.find('const') == -1:
#            self.usage = 'const ' + self.usage
         self.__must_marshal = True
         self.__call_marshal = ''
         self.__pre_marshal  = ['%s %s;' % (self.getRawName(), self.__temp_result_var)]
         self.__post_marshal = ['%s = strdup(%s.c_str());' % (self.__result_var, self.__temp_result_var)]

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
      self.generic_name = decl.getGenericName()

      self.no_ns_name = '.'.join(decl.name)
      self.usage = self.name
      # Deal with types that need special handling.
      self._checkForProblemType()

   def _checkForProblemType(self):
      full_name = self.decl.getFullNameAbstract()
      type_id   = UNKNOWN

      if full_name[0] == 'std' and full_name[1].find('basic_string', 0) != -1:
         type_id = STD_STRING
      elif full_name[0] == 'boost' and full_name[1].find('shared_ptr', 0) != 1:
         type_id = SHARED_PTR
      else:
         # XXX: Figure out if there is a simpler way of dealing with unsigned
         # integers.  It depends largely on the order that the type information
         # is returned ("int unsigned" versus "unsigned int").
         for s in full_name:
            if s.find('long long') != -1:
               if s.find('unsigned') != -1:
                  type_id = UNSIGNED_LONG_LONG
               else:
                  type_id = LONG_LONG
               break
            elif s.find('short') != -1:
               if s.find('unsigned') != -1:
                  type_id = UNSIGNED_SHORT
               else:
                  type_id = SHORT
            # Assume that a long (not a long long) is supposed to be a 32-bit
            # integer.
            elif s.find('long') != -1 or s.find('int') != -1:
               if s.find('unsigned') != -1:
                  type_id = UNSIGNED_LONG
               else:
                  type_id = LONG
               break
            # Translate char, which is 1 byte in C/C++, into byte.
            elif s.find('char') != -1:
               if s.find('unsigned') != -1:
                  type_id = UNSIGNED_CHAR
               else:
                  type_id = CHAR
               break

      # Based on type_id, process the problem type.
      if type_id != UNKNOWN:
         self._processProblemType(type_id)

   def _processProblemType(self, typeID):
      if typeID == STD_STRING:
         self.usage = 'string'
         self.problem_type = True
         self.decl.must_marshal = False
      # Translate char, which is 1 byte in C/C++, into byte.
      elif typeID == CHAR:
         self.usage = 'sbyte'
      elif typeID == UNSIGNED_CHAR:
         self.usage = 'byte'
      elif typeID == SHORT:
         self.usage = 'short'
      elif typeID == UNSIGNED_SHORT:
         self.usage = 'ushort'
      # Assume that a long (not a long long) is supposed to be a 32-bit
      # integer.
      elif typeID == LONG or typeID == INT:
         self.usage = 'int'
      elif typeID == UNSIGNED_LONG or typeID == UNSIGNED_INT:
         self.usage = 'uint'
      # Using long long probably indicates a desire for a 64-bit integer.
      elif typeID == UNSIGNED_LONG_LONG:
         self.usage = 'ulong'
      elif typeID == LONG_LONG:
         self.usage = 'long'
      elif typeID == SHARED_PTR:
         real_type_re = re.compile(r"^boost.shared_ptr<(.*)>$")
         match = real_type_re.match(self.usage)
         if None != match:
            # XXX: Once we have the type contained by the shared pointer, do
            # we need to do anything with it?
            self.usage = match.groups()[0]
         else:
            assert(False)

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
               self.usage = 'ref ' + re.sub(r"[&*]", "", self.usage)
               self.__needs_unsafe = False
            else:
               self.usage = '[MarshalAs(UnmanagedType.CustomMarshaler, MarshalTypeRef = typeof(%sMarshaler))] %s' % \
                            (self.usage, self.usage)

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
               self.__needs_unsafe = False
               self.__param_name   = 'ref ' + self.__orig_param_name
            else:
               self.__must_marshal = True
               self.__param_name = self.__orig_param_name

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

   def _processProblemType(self, typeID):
      # Perform default problem type processing first.
      CSharpVisitor._processProblemType(self, typeID)

class CSharpDelegateParamVisitor(CSharpVisitor):
   def __init__(self):
      CSharpVisitor.__init__(self)
      self.__must_marshal = False

   def visit(self, decl):
      CSharpVisitor.visit(self, decl)

      if decl.suffix == '&' or decl.suffix == '*':
         if not self.problem_type:
            if self._isFundamentalType(decl):
               self.usage = 'ref ' + re.sub(r"[&*]", "", self.usage)
               self.__must_marshal = False
            else:
               self.__must_marshal = True

   def mustMarshal(self):
      return self.__must_marshal

class CSharpReturnVisitor(CSharpVisitor):
   '''
   C# visitor for return type declarations.  This will handle the details
   associated with return types when marshaling is in effect.
   '''
   def __init__(self):
      CSharpVisitor.__init__(self)

   def visit(self, decl):
      CSharpVisitor.visit(self, decl)
