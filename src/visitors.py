# $Id: visitors.py,v 1.54 2004-05-21 21:42:37 patrick Exp $

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

def getCallbackName(methodDecl):
   '''
   Returns the name of the C callback that corresponds with the given method
   declaration.
   '''
   name = methodDecl.name[0] + '_callback'
   if len(methodDecl.parameters) > 0:
      params = [x[0].getID() for x in methodDecl.parameters]
      name = name + '_' + '_'.join(params)
   return name

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
      if cxx_name == 'std::string' or cxx_name.find('std::basic_string<', 0) != -1:
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
      return self.decl.real_type.name[0] in self.fundamental_types

class CPlusPlusParamVisitor(CPlusPlusVisitor):
   '''
   C++ visitor for function/method parameters being passed from C# into native
   code.  In other words, this class is designed to handle marshaling types
   friendly to C# into what the native function call actually expects.
   '''
   def __init__(self):
      CPlusPlusVisitor.__init__(self)
      self.__initialize()
      self.__func_name       = ''
      self.__param_name      = ''
      self.__orig_param_name = ''

   def __initialize(self):
      # Basic data members needed for parameter marshaling.
      self.__pre_marshal  = []
      self.__post_marshal = []
      self.__must_marshal = False

   def visit(self, decl):
      self.__initialize()
      CPlusPlusVisitor.visit(self, decl)

      # If the parameter is passed by reference, we need to translate that into
      # being passed as a pointer instead.
      if decl.suffix == '&':
         if not self.problem_type and not self._isFundamentalType():
            self.usage = re.sub(r"&", "*", self.name)

            self.__setMustMarshal(True)
            self.__pre_marshal  = ['%s %s = *%s;' % \
                                      (self.getRawName(), self.__param_name,
                                       self.__orig_param_name)]
#            self.__post_marshal = ['*%s = %s;' % \
#                                     (self.__orig_param_name, self.__param_name)]
         # If we have a fundamental type being passed by const reference,
         # change that to pass-by-value semantics.  The .NET code expects
         # this (it's easier to pass value types by value in C#, and literal
         # constants cannot be passed by reference).
         elif decl.const and self._isFundamentalType():
            self.usage = re.sub(r"&", "", self.name)
            self.__must_marshal = False

   def _processProblemType(self, typeID):
      # Perform default problem type processing first.
      CPlusPlusVisitor._processProblemType(self, typeID)

      if self.decl.suffix == '&' and not self.decl.const:
         self.usage += '*'

      if typeID == STD_STRING:
         # If the C++ code is expecting a non-const reference to a std::string,
         # we will receive a char** from the CLI.  We need to transform the
         # char** into a std::string and pass it to the C++ code.  The result
         # will be stored in the memory pointed to by the char**.
         if self.decl.suffix == '&' and not self.decl.const:
            self.__setMustMarshal(True)
            self.__pre_marshal  = ['std::string %s = *%s;' % \
                                     (self.__param_name, self.__orig_param_name)]
            self.__post_marshal = ['*%s = strdup(%s.c_str());' % \
                                     (self.__orig_param_name, self.__param_name)]
      elif typeID == SHARED_PTR:
         self.__param_name = '*' + self.__orig_param_name
         self.usage += '*'

   def __setMustMarshal(self, mustMarshal):
      self.__must_marshal = mustMarshal
      if mustMarshal:
         self.__param_name   = 'marshal_' + self.__orig_param_name
      else:
         self.__param_name   = self.__orig_param_name

   def mustMarshal(self):
      return self.__must_marshal

   def getParamString(self):
      return self.__param_name

   def setFunctionName(self, funcName):
      self.__func_name = funcName

   def setParamName(self, paramName):
      self.__param_name      = paramName
      self.__orig_param_name = paramName

   def getPreCallMarshalList(self):
      return self.__pre_marshal

   def getPostCallMarshalList(self):
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

         # The CLI universe has no notion of const variables (as far as I
         # know).
         self.usage = re.sub(r"const ", "", self.usage)

         if self.__must_marshal:
            return_type = re.sub(r'\*', '', self.usage)
            self.__call_marshal = self.__result_var + ' = new ' + return_type + '(%s);'
            self.__pre_marshal = []
            self.__post_marshal = []
      # If we have a type that is being returned by reference but that does not
      # require marshaling, we'll just copy it.  Since the data has to cross
      # the language boundary, there is no point in trying to retain a
      # reference.
      elif decl.suffix == '&':
         self.usage = re.sub(r"(const|&)", "", self.name)
      # If we have a type that is being returned as a pointer, we do not care
      # about preserving const-ness.  The CLI universe has no notion of const
      # variables (as far as I know).
      elif decl.suffix == '*':
         self.usage = re.sub(r"const ", "", self.name)

   def mustMarshal(self):
      return self.__must_marshal

   def getResultVarName(self):
      return self.__result_var

   def getMarshalResultVarName(self):
      return self.__temp_result_var

   def getPreCallMarshalList(self):
      return self.__pre_marshal

   def getPostCallMarshalList(self):
      return self.__post_marshal

   def getMarshaledCall(self):
      return self.__call_marshal

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

class CPlusPlusMethodParamVisitor(CPlusPlusVisitor):
   '''
   C++ visitor for adapter class method parameters.  These parameters are
   passed from native code into the CIL universe.  Unfortunately, this
   duplicates some data members of CPlusPlusParamVisitor, but it does not
   duplicate any of that class' (important) functionality.
   '''
   def __init__(self):
      CPlusPlusVisitor.__init__(self)
      self.__initialize()
      self.__func_name       = ''
      self.__param_name      = ''
      self.__orig_param_name = ''

   def __initialize(self):
      # Basic data members needed for parameter marshaling.
      self.__pre_marshal  = []
      self.__post_marshal = []
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
            self.__param_name   = '&' + self.__param_name

   def _processProblemType(self, typeID):
      # Perform default problem type processing first.
      CPlusPlusVisitor._processProblemType(self, typeID)

      if self.decl.suffix == '&' and not self.decl.const:
         self.usage += '*'

      if typeID == STD_STRING:
         self.__setMustMarshal(True)
         marshal_param = self.__param_name

         # If the std::string object is being passed by reference, we need to
         # pass a pointer to a fixed-size character array.  Once the call
         # returns, then we need to assign the result to the original
         # std::string reference.
         if self.decl.suffix == '&' and not self.decl.const:
            self.__pre_marshal  = ['char* %s = (char*) malloc(sizeof(char) * 256);' % marshal_param]
            self.__param_name   = '&' + self.__param_name
            self.__post_marshal = ['%s = %s;' % (self.__orig_param_name,
                                                 marshal_param)]
            self.__post_marshal += ['free(%s);' % marshal_param]

         # Otherwise, we make a copy of the std::string object in a char* and
         # pass that to the CIL universe.
         else:
            if self.decl.suffix == '*':
               deref_op = '->'
            else:
               deref_op = '.'
            self.__pre_marshal  = ['char* %s = strdup(%s%sc_str());' % \
                                      (marshal_param, self.__orig_param_name,
                                       deref_op)]
            self.__post_marshal = ['free(%s);' % marshal_param]

      elif typeID == SHARED_PTR:
         self.usage += '*'
         self.__must_marshal = True
         self.__param_name   = 'p_%s' % self.__orig_param_name
         # XXX: Should this memory be deleted in a post-marshal statement, or
         # does the managed run-time handle deletion?  This depends on how the
         # C# marshaling works...
         self.__pre_marshal  = ['%s* %s = new %s(%s);' % \
                                  (self.name, self.__param_name, self.name,
                                   self.__orig_param_name)]

   def __setMustMarshal(self, mustMarhsal):
      self.__must_marshal = mustMarhsal
      if mustMarhsal:
         self.__param_name   = 'marshal_' + self.__orig_param_name
      else:
         self.__param_name   = self.__orig_param_name

   def mustMarshal(self):
      return self.__must_marshal

   def getParamString(self):
      return self.__param_name

   def setFunctionName(self, funcName):
      self.__func_name = funcName

   def setParamName(self, paramName):
      self.__param_name      = paramName
      self.__orig_param_name = paramName

   def getPreCallMarshalList(self):
      return self.__pre_marshal

   def getPostCallMarshalList(self):
      return self.__post_marshal

   def needsParamHolder(self):
      return self.__needs_param_holder

   def getParamHolderDecl(self):
      assert(self.needsParamHolder())
      return self.__param_holder_decl

   def getParamHolderType(self):
      assert(self.needsParamHolder())
      return self.__param_holder_type

class CPlusPlusFunctionWrapperVisitor(CPlusPlusVisitor):
   def __init__(self):
      CPlusPlusVisitor.__init__(self)
      self.__initialize()

   def __initialize(self):
      self.__class_obj          = None
      self.__class_name         = ''
      self.__param_count        = -1
      self.__method_kind        = ''
      self.__orig_method_call   = ''
      self.__method_call        = ''
      self.__returns            = False
      self.__return_type        = ''
      self.__return_statement   = ''
      self.__param_type_list    = []
      self.__param_list         = []
      self.__pre_call_marshal   = []
      self.__post_call_marshal  = []

   def setClassInfo(self, classObj, className):
      self.__class_obj  = classObj
      self.__class_name = className

   def setCall(self, methodCall):
      self.__orig_method_call = methodCall

   def setParamCount(self, count):
      self.__param_count = count

   def visit(self, decl):
#      self.__initialize()
      CPlusPlusVisitor.visit(self, decl)

      if self.__param_count == -1:
         self.__param_count = len(decl.parameters)
      else:
         self.generic_name += str(self.__param_count)

      method_call = self.__orig_method_call
      self.__param_list = []

      # Memeber functions may be of a variety of kinds.
      if decl.member:
         # Virtual method.
         if decl.virtual:
            self.__method_kind = 'virtual'
         # Static method.
         elif decl.static:
            self.__method_kind = 'static'
         # Non-virtual, non-static method.
         else:
            self.__method_kind = 'non-virtual'

         # If this is a non-static class member function, then we need the
         # "self" parameter for the function call.
         if not decl.static:
            # We also have to deal with potential use of smart pointers.
            if self.__class_obj and self.__class_obj.info.smart_ptr:
               if self.__class_obj.info.smart_ptr_decl is not None:
                  smart_ptr = self.__class_obj.info.smart_ptr_decl % self.__class_name
               else:
                  smart_ptr = self.__class_name

               self.__param_type_list = ['%s* self_ptr' % smart_ptr]
               if self.__class_obj.info[decl.name[0]].direct_call:
                  method_call = '(*self_ptr).' + self.__orig_method_call
               else:
                  method_call = '(*self_ptr)->' + self.__orig_method_call
            else:
               self.__param_type_list = ['%s* self_' % self.__class_name]
               method_call = 'self_->' + self.__orig_method_call

      # Handle the result type before all the parameter stuff.
      result_visitor = CPlusPlusReturnVisitor()
      decl.result.accept(result_visitor)
      self.__return_type = result_visitor.getUsage()
      self.__returns = self.__return_type != 'void'

      param_visitor = CPlusPlusParamVisitor()

      for i in range(self.__param_count):
         p = decl.parameters[i]
         param_visitor.setParamName(p[1])
         p[0].accept(param_visitor)

         param_type = param_visitor.getUsage()

         if param_visitor.mustMarshal():
            self.__pre_call_marshal  += param_visitor.getPreCallMarshalList()
            self.__post_call_marshal += param_visitor.getPostCallMarshalList()

         self.__param_list.append(param_visitor.getParamString())
         self.__param_type_list.append(param_type + ' ' + p[1])

      assert(decl.info is not None)

      # If this method returns an array, we have to change the behavior of the
      # C wrapper function significantly.  Instead of returning a pointer
      # (array), the C wrapper returns nothing.  A new parameter is added to
      # the wrapper's list of parameters that will be used to store a copy of
      # the array returned by the C++ method/function we want to call.
      if decl.info.return_array:
         self.__return_type = 'void'
         self.__returns = False

         # Strip out constness from the array type.
         temp_type = re.sub('const ', '', result_visitor.getRawName())
         self.__param_type_list.append(temp_type + ' arrayHolder')

         declare_temp = '%s temp_array;' % result_visitor.getRawName()
         self.__pre_call_marshal.append(declare_temp)
         loop_decl = 'for ( int i = 0; i < %s; ++i )' % decl.info.return_array
         self.__post_call_marshal.append(loop_decl)
         self.__post_call_marshal.append('{')
         self.__post_call_marshal.append('   arrayHolder[i] = temp_array[i];')
         self.__post_call_marshal.append('}')

      arg_list = ', '.join(self.__param_list)

      # A semi-colon cannot go at the end of this statement yet because of
      # the weird way that I wrote CPlusPlusReturnVisitor.getMarshaledCall().
      method_call = ['%s(%s)' % (method_call, arg_list)]

      # If the method returns, add that information.
      if self.returns():
         method_call.insert(0, '%s result;' % self.__return_type)

         # XXX: This is a mess.  CPlusPlusReturnVisitor needs a lot of work.
         if result_visitor.mustMarshal():
            self.__pre_call_marshal  += result_visitor.getPreCallMarshalList()
            self.__post_call_marshal += result_visitor.getPostCallMarshalList()

            if result_visitor.getMarshaledCall():
               method_call[1] = result_visitor.getMarshaledCall() % method_call[1]
            else:
               method_call[1] = '%s = %s;' % (result_visitor.getMarshalResultVarName(),
                                              method_call[1])
         else:
            method_call[1] = 'result = %s;' % method_call[1]

         self.__return_statement = 'return result;'
      elif decl.info.return_array:
         method_call[0] = 'temp_array = ' + method_call[0] + ';'
      else:
         method_call[0] += ';'

      self.__method_call = method_call

   def getKind(self):
      return self.__method_kind

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

   def getCallLines(self):
      return self.__method_call

   def getPostCallMarshalList(self):
      return self.__post_call_marshal

   def getReturnStatement(self):
      assert(self.returns())
      return self.__return_statement

class CPlusPlusConstructorWrapperVisitor(CPlusPlusVisitor):
   def __init__(self):
      CPlusPlusVisitor.__init__(self)
      self.__initialize()

   def __initialize(self):
      self.__class_obj         = None
      self.__raw_class_name    = ''
      self.__class_name        = ''
      self.__param_count       = -1
      self.__method_call       = []
      self.__return_type       = ''
      self.__param_type_list   = []
      self.__param_list        = []
      self.__pre_call_marshal  = []
      self.__post_call_marshal = []

   def setClassInfo(self, classObj, rawClassName, className):
      self.__class_obj      = classObj
      self.__raw_class_name = rawClassName
      self.__class_name     = className

      self.__return_type = self.__class_name + '*'

   def setParamCount(self, count):
      self.__param_count = count

   def visit(self, decl):
      CPlusPlusVisitor.visit(self, decl)

      if self.__param_count == -1:
         self.__param_count = len(decl.parameters)
      else:
         self.generic_name += str(self.__param_count)

      self.__param_list = []

      param_visitor = CPlusPlusParamVisitor()

      for i in range(self.__param_count):
         p = decl.parameters[i]
         param_visitor.setParamName(p[1])
         p[0].accept(param_visitor)

         param_type = param_visitor.getUsage()

         if param_visitor.mustMarshal():
            self.__pre_call_marshal  += param_visitor.getPreCallMarshalList()
            self.__post_call_marshal += param_visitor.getPostCallMarshalList()

         self.__param_list.append(param_visitor.getParamString())
         self.__param_type_list.append(param_type + ' ' + p[1])

      arg_list = ', '.join(self.__param_list)

      if self.__class_obj.info.smart_ptr:
         if self.__class_obj.info.smart_ptr_decl is not None:
            smart_ptr = self.__class_obj.info.smart_ptr_decl % self.__raw_class_name
         else:
            smart_ptr = self.__raw_class_name

         if self.__class_obj.info.ref_counted:
            method_call = ['%s* obj = new %s(new %s(%s));' % \
                              (smart_ptr, smart_ptr, self.__class_name, arg_list)]
         else:
            method_call = ['%s* obj = new %s(%s(%s));' % \
                              (smart_ptr, smart_ptr, self.__class_name, arg_list)]

         self.__return_type = smart_ptr + '*'
      else:
         obj_ref = 'obj'
         method_call = ['%s* obj = new %s(%s);' % \
                           (self.__class_name, self.__class_name, arg_list)]

      if self.__class_obj.needsAdapter():
         class_visitor = CPlusPlusVisitor()
         self.__class_obj.class_.accept(class_visitor)
         adapter_name = class_visitor.getGenericName() + '_Adapter'
         del class_visitor
      else:
         adapter_name = self.__raw_class_name

      # Add the information relating to the virtual methods defined by this
      # constructor's class.
      for i in range(len(self.__class_obj.virtual_methods)):
         cb_name = getCallbackName(self.__class_obj.virtual_methods[i])
         cb_param_type = '%s::%s_t cb%d' % (adapter_name, cb_name, i)
         self.__param_type_list.append(cb_param_type)
         method_call.append('%s->%s = cb%d;' % (obj_ref, cb_name, i))

      # Add the information relating to the virtual methods inherited from this
      # constructor's parent class(es).
      for i in range(len(self.__class_obj.inherited_virtual_methods)):
         cb_name = getCallbackName(self.__class_obj.inherited_virtual_methods[i])
         cb_param_num = i + len(self.__class_obj.virtual_methods)
         cb_param_type = '%s::%s_t cb%d' % \
                            (adapter_name, cb_name, cb_param_num)
         self.__param_type_list.append(cb_param_type)
         method_call.append('%s->%s = cb%d;' % (obj_ref, cb_name, cb_param_num))

      self.__method_call = method_call

   def getReturnType(self):
      return self.__return_type

   def getParamTypeList(self):
      return self.__param_type_list

   def getParamList(self):
      return self.__param_list

   def getPreCallMarshalList(self):
      return self.__pre_call_marshal

   def getCallLines(self):
      return self.__method_call

   def getPostCallMarshalList(self):
      return self.__post_call_marshal

class CPlusPlusAdapterMethodVisitor(CPlusPlusVisitor):
   '''
   Visitor for methods that appear in C++ adapter classes for those classes
   being exposed to C# that have virtual methods.  This visitor can handle
   different method types (virtual, non-virtual, and static), but its
   functionality is solely for the methods defined in C++ adapter classes.
   '''
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
      "Returns the return type for a virtual method's callback typedef."
      result_decl = self.decl.result
      marshal_str = result_decl.getFullCPlusPlusName()
      if result_decl.must_marshal and result_decl.suffix != '*':
         marshal_str += '*'

      if marshal_str == 'std::string' or marshal_str.find('basic_string') != -1:
         marshal_str = 'char*'

      return marshal_str

   def visit(self, decl):
      self.__initialize()
      CPlusPlusVisitor.visit(self, decl)

      # Handle the result type first.
      result_visitor = CPlusPlusReturnVisitor()
      decl.result.accept(result_visitor)
      self.__return_type = result_visitor.getRawName()

      self.__returns = self.__return_type != 'void'

      callback_param_types = []
      param_visitor = CPlusPlusMethodParamVisitor()
      for p in self.decl.parameters:
         param_visitor.setFunctionName(self.getGenericName())
         param_visitor.setParamName(p[1])
         p[0].accept(param_visitor)

         param_type = param_visitor.getRawName()
         callback_param_type = param_visitor.getUsage()

         # If this parameter needs a holder, we must declare the holder type.
         # The type of this parameter used in the callback will be a pointer to
         # the holder type.
         if param_visitor.needsParamHolder():
            self.__param_holder_decls.append(param_visitor.getParamHolderDecl())
            callback_param_type = '%s*' % param_visitor.getParamHolderType()

         if param_visitor.mustMarshal():
            self.__pre_call_marshal  += param_visitor.getPreCallMarshalList()
            self.__post_call_marshal += param_visitor.getPostCallMarshalList()

         self.__param_list.append(param_visitor.getParamString())
         self.__param_type_list.append(param_type + ' ' + p[1])
         callback_param_types.append(callback_param_type)

      arg_list = ', '.join(self.__param_list)

      # Start method_call out by making it a call to the base class
      # method that we are overriding.  In other words, we begin with a
      # pass-through method, and we alter it to behave differently below if
      # necessary.
      method_call = self.__orig_method_call % (self.decl.getFullCPlusPlusName(),
                                               arg_list)

      # Only work out the callback information if we're actually going to have
      # a callback.
      if self.needsCallback():
         callback_return_type = self.__getCallbackResultType()
         self.__callback_name = getCallbackName(self.decl)
         self.__callback_typedef = 'typedef %s (*%s_t)(%s);' % \
                                      (callback_return_type,
                                       self.__callback_name,
                                       ', '.join(callback_param_types))

         method_call = self.__orig_method_call % (self.__callback_name, arg_list)

         # Since we have a callback in place, we may need to marshal the return
         # type from the callback.
         if result_visitor.mustMarshal() and callback_return_type != 'char*':
            method_call = '*(%s)' % method_call

      if self.returns():
         method_call = '%s result = %s' % (self.__return_type, method_call)
         self.__return_statement = 'return result'

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

      if cxx_name == 'std::string' or cxx_name.find('std::basic_string<', 0) != -1:
         type_id = STD_STRING
      elif cxx_name.find('boost::shared_ptr<', 0) != -1:
         type_id = SHARED_PTR
      else:
         if cxx_name == 'long long unsigned int':
            type_id = UNSIGNED_LONG_LONG
         elif cxx_name == 'long long int':
            type_id = LONG_LONG
         elif cxx_name == 'short':
            type_id = SHORT
         elif cxx_name == 'unsigned short' or cxx_name == 'short unsigned int':
            type_id = UNSIGNED_SHORT
         elif cxx_name == 'long' or cxx_name == 'int':
            type_id = LONG
         # Assume that a long (not a long long) is supposed to be a 32-bit
         # integer.
         elif cxx_name == 'unsigned long' or cxx_name == 'unsigned int':
            type_id = UNSIGNED_LONG
         elif cxx_name == 'char':
            type_id = CHAR
         # Translate char, which is 1 byte in C/C++, into byte.
         elif cxx_name == 'unsigned char':
            type_id = UNSIGNED_CHAR

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
         match = self.real_type_re.search(self.decl.getCPlusPlusName())
         if match is not None:
            # XXX: Once we have the type contained by the shared pointer, do
            # we need to do anything with it?
            # XXX: This is a hack to deal with simple cases for the near term.
            cxx_template_param = match.groups()[0]
            self.usage = '.'.join(cxx_template_param.split('::'))
         else:
            assert(False)

   def _isFundamentalType(self, decl):
      return self.usage in self.fundamental_types

class CSharpVariableVisitor(CSharpVisitor):
   re_value_float = re.compile(r'f$')

   def __init__(self):
      CSharpVisitor.__init__(self)

   def visit(self, decl):
      CSharpVisitor.visit(self, decl.type)

      self.variable_name = decl.name[0]

      if self.getUsage() == 'float' and not self.re_value_float.search(decl.init_value):
         self.init_value = decl.init_value + 'f'
      else:
         self.init_value = decl.init_value

   def getName(self):
      return self.variable_name

   def getValue(self):
      return self.init_value

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
               self.usage = re.sub(r"[&*]", "", self.usage)

               # Do not bother with passing fundamental types by reference if
               # the native code expects a const reference.
               if not decl.const:
                  self.usage = 'ref ' + self.usage

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
      self.__pre_marshal  = []
      self.__post_marshal = []
      self.__must_marshal = False
      self.__needs_unsafe = False

   def visit(self, decl):
      self.__initialize()
      CSharpVisitor.visit(self, decl)

      if decl.suffix == '&' or decl.suffix == '*':
         if not self.problem_type:
            if decl.type_decl.type_str == 'enumeration':
#               self.usage = re.sub(r"[&*]", "", self.usage)
               self.__setMustMarshal(False)
            elif self._isFundamentalType(decl):
               self.usage = re.sub(r"[&*]", "", self.usage)

               # Do not bother with passing fundamental types by reference if
               # the native code expects a const reference.
               if decl.const:
                  self.__setMustMarshal(False)
                  self.__needs_unsafe = False
               else:
                  self.usage = 'ref ' + self.usage
                  self.__must_marshal = True
                  self.__needs_unsafe = False
                  self.__param_name   = 'ref ' + self.__orig_param_name
            else:
               self.__must_marshal = True
               self.__param_name = self.__orig_param_name

   def __setMustMarshal(self, mustMarshal):
      self.__must_marshal = mustMarshal
      if mustMarshal:
         self.__param_name   = 'marshal_' + self.__orig_param_name
      else:
         self.__param_name   = self.__orig_param_name

   def mustMarshal(self):
      return self.__must_marshal

   def needsUnsafe(self):
      return self.__needs_unsafe

   def getParamString(self):
      return self.__param_name

   # XXX: This parameter name stuff sucks.
   def setParamName(self, paramName):
      self.__orig_param_name = paramName
      self.__param_name      = paramName

   def getPreCallMarshalList(self):
      return self.__pre_marshal

   def getPostCallMarshalList(self):
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
               self.usage = re.sub(r"[&*]", "", self.usage)

               # Do not bother with passing fundamental types by reference if
               # the native code expects a const reference.
               if not decl.const:
                  self.usage = 'ref ' + self.usage

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

class CSharpMethodVisitor(CSharpVisitor):
   def __init__(self):
      CSharpVisitor.__init__(self)
      self.__initialize()

   def __initialize(self):
      self.__param_count              = -1
      self.__has_base_class           = False
      self.__sealed_class             = False
      self.__method_kind              = ''
      self.__needs_delegate           = False
      self.__delegate_name            = ''
      self.__delegate_param_type_list = []
      self.__method_call              = []
      self.__returns                  = False
      self.__return_type              = ''
      self.__return_statement         = ''
      self.__pi_param_type_list       = []
      self.__pinvoke_decl             = ''
      self.__param_type_list          = []
      self.__param_list               = []
      self.__pre_call_marshal         = []
      self.__post_call_marshal        = []

   def setSealed(self, sealed):
      self.__sealed_class = sealed

   def setParamCount(self, count):
      self.__param_count = count

   def setHasBaseClass(self, hasBase):
      self.__has_base_class = hasBase

   def visit(self, decl):
      CSharpVisitor.visit(self, decl)

      if self.__param_count == -1:
         self.__param_count = len(decl.parameters)
      else:
         self.generic_name += str(self.__param_count)

      self.__pi_param_type_list = []
      self.__param_list         = []

      if decl.member:
         # Determine if we need a delegate right away so that code below can
         # take advantage of that knowledge.
         # If our class is sealed, we do not need to declare a delegate.
         # If this method is virtual and not an override of a non-abstract
         # method, then we need a delegate and member variable to hold the
         # delegate.
         # XXX: Can this expression be simplified?
         if not self.__sealed_class and \
            ((decl.virtual and not decl.override) or \
             (decl.virtual and not self.__has_base_class)):
            self.__needs_delegate = True
            self.__delegate_name  = th.getDelegateName(self.decl)

         # Virtual method.
         if decl.virtual:
            if decl.override and self.__has_base_class:
               self.__method_kind = 'override'
            elif self.__sealed_class:
               self.__method_kind =  ''
            else:
               self.__method_kind = 'virtual'
         # Static method.
         elif decl.static:
            self.__method_kind = 'static'
            if decl.override:
               self.__method_kind = 'new static'
         # Non-virtual, non-static method.
         else:
            if decl.override:
               self.__method_kind = 'new'

         if not decl.static:
            self.__pi_param_type_list = ['IntPtr obj']
            self.__param_list         = ['mRawObject']
      else:
         self.__method_kind = 'static'

      # Handle the result type before all the parameter stuff.
      result_visitor = CSharpReturnVisitor()
      decl.result.accept(result_visitor)
      self.__return_type = result_visitor.getUsage()

      self.__returns = self.__return_type != 'void'

      param_visitor     = CSharpParamVisitor()
      dlg_param_visitor = CSharpDelegateParamVisitor()
      pi_param_visitor  = CSharpPInvokeParamVisitor()

      unsafe = False

      for i in range(self.__param_count):
         p = decl.parameters[i]
         param_visitor.setParamName(p[1])
         p[0].accept(param_visitor)
         p[0].accept(pi_param_visitor)

         param_type = param_visitor.getUsage()

         if param_visitor.mustMarshal():
            self.__pre_call_marshal  += param_visitor.getPreCallMarshalList()
            self.__post_call_marshal += param_visitor.getPostCallMarshalList()

         self.__param_list.append(param_visitor.getParamString())

         if self.needsDelegate():
            p[0].accept(dlg_param_visitor)
   
            if dlg_param_visitor.mustMarshal():
               marshaler_name = dlg_param_visitor.getUsage() + 'Marshaler'
               delegate_param_type = \
                  '[MarshalAs(UnmanagedType.CustomMarshaler, MarshalTypeRef = typeof(%s))] %s %s' % \
                     (marshaler_name, dlg_param_visitor.getUsage(), p[1])
            else:
               delegate_param_type = '%s %s' % (dlg_param_visitor.getUsage(), p[1])

            self.__delegate_param_type_list.append(delegate_param_type)

         if not unsafe and pi_param_visitor.needsUnsafe():
            unsafe = True

         self.__param_type_list.append(param_type + ' ' + p[1])
         self.__pi_param_type_list.append('%s %s' % (pi_param_visitor.getUsage(), p[1]))

      del dlg_param_visitor

      if unsafe:
         unsafe_str = 'unsafe '
      else:
         unsafe_str = ''

      assert(decl.info is not None)

      # If this method returns an array, we have to change the signature of the
      # P/Invoke function.  Instead of returning a pointer, the call returns
      # nothing.  A new parameter is added to the P/Invoke function's list of
      # parameters that will be used to store a copy of the array returned by
      # the C++ method/function we want to call.
      if decl.info.return_array:
         pinvoke_return = 'void'

         # Strip out constness from the array type.
         temp_type = re.sub('const ', '', result_visitor.getRawName())
         temp_param_pi = '[In, Out] %s[] arrayHolder' % temp_type
         self.__pi_param_type_list.append(temp_param_pi)
         self.__param_list.append('array_holder')

         declare_temp = '%s[] array_holder = new %s[%d]' % \
                           (temp_type, temp_type, decl.info.return_array)
         self.__pre_call_marshal.append(declare_temp)
      else:
         pinvoke_return = result_visitor.getUsage()

      pinvoke_name = self.getGenericName()

      pinvoke_decl_params = ',\n\t'.join(self.__pi_param_type_list)
      self.__pinvoke_decl = 'private %sextern static %s %s(%s)' % \
                            (unsafe_str, pinvoke_return,
                             pinvoke_name, pinvoke_decl_params)

      arg_list = ', '.join(self.__param_list)

      # Start method_call out by making it a call to the P/Invoke function.
      method_call = ['%s(%s);' % (pinvoke_name, arg_list)]

      if decl.info.return_array:
         self.__return_statement = 'return array_holder'
         self.__return_type += '[]'
      # If the method returns, add that information.
      elif self.returns():
         method_call.insert(0, '%s result;' % self.__return_type)
         method_call[1] = 'result = %s' % method_call[1]
         self.__return_statement = 'return result'

      # If the method is marked as unsafe, wrap the call in an 'unsafe' block.
      if unsafe:
         method_call.insert(1, 'unsafe {')
         method_call.append('}')

      self.__method_call = method_call

   def needsDelegate(self):
      return self.__needs_delegate

   def getDelegateName(self):
      assert(self.needsDelegate())
      return self.__delegate_name

   def getDelegateParamTypeList(self):
      assert(self.needsDelegate())
      return self.__delegate_param_type_list

   def getPInvokeDecl(self):
      return self.__pinvoke_decl

   def getKind(self):
      return self.__method_kind

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

   def getMethodCallLines(self):
      return self.__method_call

   def getPostCallMarshalList(self):
      return self.__post_call_marshal

   def getReturnStatement(self):
      assert(self.returns())
      return self.__return_statement

class CSharpConstructorVisitor(CSharpVisitor):
   def __init__(self):
      CSharpVisitor.__init__(self)
      self.__initialize()

   def __initialize(self):
      self.__param_count              = -1
      self.__class_obj                = None
      self.__pi_param_type_list       = []
      self.__param_type_list          = []
      self.__param_list               = []
      self.__pre_call_marshal         = []
      self.__post_call_marshal        = []

   def setClassInfo(self, classObj):
      self.__class_obj = classObj

   def setParamCount(self, count):
      self.__param_count = count

   def visit(self, decl):
      CSharpVisitor.visit(self, decl)

      if self.__param_count == -1:
         self.__param_count = len(decl.parameters)
      else:
         self.generic_name += str(self.__param_count)

      self.__pi_param_type_list = []
      self.__param_list         = []

      param_visitor     = CSharpParamVisitor()
      pi_param_visitor  = CSharpPInvokeParamVisitor()

      for i in range(self.__param_count):
         p = decl.parameters[i]
         param_visitor.setParamName(p[1])
         p[0].accept(param_visitor)
         p[0].accept(pi_param_visitor)

         param_type = param_visitor.getUsage()

         if param_visitor.mustMarshal():
            self.__pre_call_marshal  += param_visitor.getPreCallMarshalList()
            self.__post_call_marshal += param_visitor.getPostCallMarshalList()

         self.__param_list.append(param_visitor.getParamString())
         self.__param_type_list.append(param_type + ' ' + p[1])
         self.__pi_param_type_list.append('%s %s' % (pi_param_visitor.getUsage(), p[1]))

      for i in range(len(self.__class_obj.virtual_methods)):
         method = self.__class_obj.virtual_methods[i]
         delegate_name = th.getDelegateName(method)
         param_decl = '[MarshalAs(UnmanagedType.FunctionPtr)] %s d%d' % (delegate_name, i)
         self.__pi_param_type_list.append(param_decl)

      for i in range(len(self.__class_obj.inherited_virtual_methods)):
         method = self.__class_obj.inherited_virtual_methods[i]
         delegate_name = th.getDelegateName(method)
         param_num = i + len(self.__class_obj.virtual_methods)
         param_decl = '[MarshalAs(UnmanagedType.FunctionPtr)] %s d%d' % (delegate_name, param_num)
         self.__pi_param_type_list.append(param_decl)

   def getParamTypeList(self):
      return self.__param_type_list

   def getParamList(self):
      return self.__param_list
   
   def getPInvokeParamTypeList(self):
      return self.__pi_param_type_list

   def getPreCallMarshalList(self):
      return self.__pre_call_marshal

   def getPostCallMarshalList(self):
      return self.__post_call_marshal
