# $Id: visitors.py,v 1.30 2004-01-26 22:16:56 patrick Exp $

import re
import TemplateHelpers as th

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
AUTO_PTR           = 12
CUSTOM_SMART_PTR   = 13

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
      self.name         = decl.getFullCPlusPlusName()
      self.generic_name = decl.getID()
      self.no_ns_name   = '::'.join(decl.name)
      self.usage        = self.name

      # Deal with types that need special handling.
      self._checkForProblemType()

   def _checkForProblemType(self):
      cxx_name = self.decl.getCPlusPlusName()
      if cxx_name.find('std::basic_string', 0) != -1:
         self._processProblemType(STD_STRING)
      elif cxx_name.find('boost::shared_ptr', 0) != -1:
         self._processProblemType(SHARED_PTR)

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
      self.__func_name       = ''
      self.__param_name      = ''
      self.__orig_param_name = ''

   def __initialize(self):
      # Basic data members needed for parameter marshaling.
      self.__pre_marshal  = ''
      self.__post_marshal = ''
      self.__must_marshal = False

      # Data members needed for parameter holder objects.
      self.__needs_param_holder = False
      self.__param_holder_type  = ''
      self.__param_holder_decl  = ''

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
      elif typeID == SHARED_PTR:
         self.__needs_param_holder = True
         self.__param_holder_type  = 'holder_%s_%s' % \
                                        (self.__orig_param_name,
                                         self.__func_name)
         self.__param_holder_decl  = 'struct %s { %s mPtr; };' % \
                                        (self.__param_holder_type,
                                         self.decl.getCPlusPlusName())

         self.__must_marshal = True
         self.__pre_marshal  = '%s* h = new %s; h->mPtr = %s' % \
                                  (self.__param_holder_type,
                                   self.__param_holder_type,
                                   self.__orig_param_name)
         self.__post_marshal = ''
         self.__param_name   = 'h'

   def mustMarshal(self):
      return self.__must_marshal

   def getMarshalParamName(self):
      assert(self.mustMarshal())
      return self.__param_name

   def setFunctionName(self, funcName):
      self.__func_name = funcName

   def setParamName(self, paramName):
      self.__param_name = 'marshal_' + paramName
      self.__orig_param_name = paramName

   def getPreCallMarshal(self):
      assert(self.mustMarshal())
      return self.__pre_marshal

   def getPostCallMarshal(self):
      assert(self.mustMarshal())
      return self.__post_marshal

   def needsParamHolder(self):
      return self.__needs_param_holder

   def getParamHolderDecl(self):
      assert(self.needsParamHolder())
      return self.__param_holder_decl

   def getParamHolderType(self):
      assert(self.needsParamHolder())
      return self.__param_holder_type

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

      # Marshaling a return type means returning a pointer.
      if decl.must_marshal:
         # If we are already returning a pointer, we do not actually need to
         # take any further steps to marshal the data.
         if decl.suffix == '*':
            self.__must_marshal = False
         # If we are returning a reference, we must instead return a pointer.
         elif decl.suffix == '&':
            self.__must_marshal = True
            self.usage = re.sub(r"&", "*", self.name)
         # For all other cases, we must return a pointer.
         else:
            self.__must_marshal = True
            self.usage += '*'

         if self.__must_marshal:
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

class CPlusPlusMethodVisitor(CPlusPlusVisitor):
   def __init__(self):
      CPlusPlusVisitor.__init__(self)
      self.__initialize()

   def __initialize(self):
      self.__orig_method_call   = '%s(%s)'
      self.__method_call        = ''
      self.__callback_name      = ''
      self.__callback_typedef   = ''
      self.__returns            = False
      self.__return_type        = ''
      self.__return_statement   = ''
      self.__param_holder_decls = []
      self.__param_type_list    = []
      self.__param_list         = []
      self.__pre_call_marshal   = []
      self.__post_call_marshal  = []

   def setMethodCall(self, methodCall):
      self.__orig_method_call = methodCall

   def __getCallbackResultType(self):
      result_decl = self.decl.result
      if result_decl.must_marshal and result_decl.suffix != '*':
         marshal_ptr = '*'
      else:
         marshal_ptr = ''
      return result_decl.getFullCPlusPlusName() + marshal_ptr

   def visit(self, decl):
      self.__initialize()
      CPlusPlusVisitor.visit(self, decl)

      # Handle the result type first.
      result_visitor = CPlusPlusReturnVisitor()
      decl.result.accept(result_visitor)
      self.__return_type = result_visitor.getRawName()

      self.__returns = self.__return_type != 'void'

      callback_param_types = []
      param_visitor = CPlusPlusParamVisitor()
      for p in self.decl.parameters:
         param_visitor.setFunctionName(self.getGenericName())
         param_visitor.setParamName(p[1])
         p[0].accept(param_visitor)

         param_type = param_visitor.getUsage()
         callback_param_type = param_type

         # If this parameter needs a holder, we must declare the holder type.
         # The type of this parameter used in the callback will be a pointer to
         # the holder type.
         if param_visitor.needsParamHolder():
            self.__param_holder_decls.append(param_visitor.getParamHolderDecl())
            callback_param_type = '%s*' % param_visitor.getParamHolderType()

         if param_visitor.mustMarshal():
            self.__pre_call_marshal.append(param_visitor.getPreCallMarshal())
            self.__post_call_marshal.append(param_visitor.getPostCallMarshal())
            self.__param_list.append(param_visitor.getMarshalParamName())
         else:
            self.__param_list.append(p[1])

         self.__param_type_list.append(param_type + ' ' + p[1])
         callback_param_types.append(callback_param_type)

      # Only work out the callback information if we're actually going to have
      # a callback.
      if self.needsCallback():
         self.__callback_name = th.getCallbackName(self.decl)
         self.__callback_typedef = 'typedef %s (*%s_t)(%s);' % \
                                      (self.__getCallbackResultType(),
                                       self.__callback_name,
                                       ', '.join(callback_param_types))

      arg_list = ', '.join(self.__param_list)
      method_call = self.__orig_method_call % (self.__callback_name, arg_list)
      if result_visitor.mustMarshal():
         method_call = '*(%s)' % method_call

      if self.returns():
         method_call = result_visitor.getMethodCall(method_call, '      ')
         self.__return_statement = 'return ' + result_visitor.getResultVarName()

      self.__method_call = method_call

   def getParamHolderDecls(self):
      return self.__param_holder_decls

   def needsCallback(self):
      return self.decl.virtual

   def getCallbackName(self):
      assert(self.needsCallback())
      return self.__callback_name

   def getCallbackTypedef(self):
      assert(self.needsCallback())
      return self.__callback_typedef

   def returns(self):
      return self.__returns

   def getReturnType(self):
      return self.__return_type

   def getParamTypeList(self):
      return self.__param_type_list

   def getParamList(self):
      return self.__param_list

   def getPreCallMarshalList(self):
      return self.__pre_call_marshal

   def getMethodCall(self):
      return self.__method_call

   def getPostCallMarshalList(self):
      return self.__post_call_marshal

   def getReturnStatement(self):
      assert(self.returns())
      return self.__return_statement

class CSharpVisitor(DeclarationVisitor):
   '''
   Basic, general-purpose C# visitor.
   '''
   
   fundamental_types = ['bool', 'byte', 'sbyte', 'char', 'short', 'ushort',
                        'int', 'uint', 'long', 'ulong', 'float', 'double']

   def __init__(self):
      DeclarationVisitor.__init__(self)

   template_match = re.compile(r'<[^>]+>')

   def visit(self, decl):
      self.decl         = decl
      self.problem_type = False

      self.name = '.'.join(decl.getFullAbstractName())
      self.generic_name = decl.getID()

      self.no_ns_name = '.'.join(decl.name)

      # If self.name contains template parameters, then we cannot use it as
      # the usage name.  We must use self.generic_name instead.
      # XXX: This seems pretty clunky.
      if self.template_match.search(self.name) != None:
         self.usage = '.'.join(decl.name)
      else:
         self.usage = self.name

      # Deal with types that need special handling.
      self._checkForProblemType()

   def _checkForProblemType(self):
      cxx_name = self.decl.getCPlusPlusName()
      type_id  = UNKNOWN

      if cxx_name.find('std::basic_string', 0) != -1:
         type_id = STD_STRING
      elif cxx_name.find('boost::shared_ptr', 0) != -1:
         type_id = SHARED_PTR
      else:
         # XXX: Figure out if there is a simpler way of dealing with unsigned
         # integers.  It depends largely on the order that the type information
         # is returned ("int unsigned" versus "unsigned int").
         if cxx_name.find('long long') != -1:
            if cxx_name.find('unsigned') != -1:
               type_id = UNSIGNED_LONG_LONG
            else:
               type_id = LONG_LONG
         elif cxx_name.find('short') != -1:
            if cxx_name.find('unsigned') != -1:
               type_id = UNSIGNED_SHORT
            else:
               type_id = SHORT
         # Assume that a long (not a long long) is supposed to be a 32-bit
         # integer.
         elif cxx_name.find('long') != -1 or cxx_name.find('int') != -1:
            if cxx_name.find('unsigned') != -1:
               type_id = UNSIGNED_LONG
            else:
               type_id = LONG
         # Translate char, which is 1 byte in C/C++, into byte.
         elif cxx_name.find('char') != -1:
            if cxx_name.find('unsigned') != -1:
               type_id = UNSIGNED_CHAR
            else:
               type_id = CHAR

      # Based on type_id, process the problem type.
      if type_id != UNKNOWN:
         self._processProblemType(type_id)

   # Regular expression for extracting the real type from a shared pointer.
   # It is declared here so that it is compiled only once.
   # XXX: Note that this regular expression should be anchored at the
   # beginning of the line, but cppdom_boost::shared_ptr<T> breaks that.  Grr...
   real_type_re = re.compile(r"boost::shared_ptr<\s*(.*)\s*>$")

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
         match = self.real_type_re.search(self.decl.cxx_name)
         if None != match:
            # XXX: Once we have the type contained by the shared pointer, do
            # we need to do anything with it?
            # XXX: This is a hack to deal with simple cases for the near term.
            cxx_template_param = match.groups()[0]
            self.usage = '.'.join(cxx_template_param.split('::'))
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

   def __toCustomMarshaler(self, usage):
      '''
      Returns a usage string for this P/Invoke parameter that includes custom
      marshaling information.
      '''
      assert(usage.find('<') == -1)
      return '[MarshalAs(UnmanagedType.CustomMarshaler, MarshalTypeRef = typeof(%sMarshaler))] %s' % \
             (usage, usage)

   def visit(self, decl):
      CSharpVisitor.visit(self, decl)

      if decl.suffix == '&' or decl.suffix == '*':
         if not self.problem_type and not decl.type_decl.type_str == 'enumeration':
            if self._isFundamentalType(decl):
               self.usage = 'ref ' + re.sub(r"[&*]", "", self.usage)
               self.__needs_unsafe = False
            else:
               self.usage = self.__toCustomMarshaler(self.usage)

   def _processProblemType(self, typeID):
      CSharpVisitor._processProblemType(self, typeID)

      if typeID == SHARED_PTR:
         self.usage = self.__toCustomMarshaler(self.usage)

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
            if decl.type_decl.type_str == 'enumeration':
#               self.usage = re.sub(r"[&*]", "", self.usage)
               self.__must_marshal = False
               self.__param_name   = self.__orig_param_name
            elif self._isFundamentalType(decl):
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
      else:
         self.__must_marshal = decl.must_marshal

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
