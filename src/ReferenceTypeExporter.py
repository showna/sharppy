# This is derived from the Pyste version of ClassExporter.py.
# See http://www.boost.org/ for more information.

# $Id: ReferenceTypeExporter.py,v 1.56 2004-01-09 20:20:34 patrick Exp $

# For Python 2.1 compatibility.
#from __future__ import nested_scope

import exporters
import Exporter
import declarations
import policies
import EnumExporter
import utils
import copy
import exporterutils
import os
import sys
import re

import Cheetah.Template as ct


#==============================================================================
# ReferenceTypeExporter
#==============================================================================
class ReferenceTypeExporter(Exporter.Exporter):
   'Generates C# P/Invoke bridging code to export a class declaration.'

   cxx_adapter_template_file = os.path.dirname(__file__) + '/class_cxx_adapter.tmpl'
   c_wrapper_template_file   = os.path.dirname(__file__) + '/class_cxx.tmpl'
   csharp_template_file      = os.path.dirname(__file__) + '/class_cs.tmpl'
 
   def __init__(self, info, parser_tail=None):
      Exporter.Exporter.__init__(self, info, parser_tail)

      self.cxx_adapter_template = ct.Template(file = self.cxx_adapter_template_file)
      self.c_wrapper_template = ct.Template(file = self.c_wrapper_template_file)
      self.csharp_template = ct.Template(file = self.csharp_template_file)

      self.export_methods_run = False

      # Abstract data information for the reference type to be exported.
      self.no_init             = False
      self.non_copyable        = False
      self.bases               = []
      self.constructors        = []
      self.non_virtual_methods = []
      self.static_methods      = []
      self.virtual_methods     = []
      self.member_operators    = []
      self.global_operators    = []

      self.protected_static_methods      = []
      self.protected_non_virtual_methods = []

      self.inherited_virtual_methods = []
      self.virtual_method_callbacks  = []

      # Nested types.
      self.nested_classes = []
      self.nested_enums   = []

      # Data members.
      self.static_members     = []
      self.non_static_members = []

   def getClassName(self):
      return utils.makeid(self.class_.FullName())

   def isInterface(self):
      '''
      Determines whether the class associated with can be considered an
      interface or not.  Being an interface means having nothing but abstract
      (pure virtual) method declarations in the class body.
      '''
      return self.class_.isInterface()

   def Name(self):
      return self.info.name

   def SetDeclarations(self, declList):
      Exporter.Exporter.SetDeclarations(self, declList)
      if self.declarations:
         decl = self.GetDeclaration(self.info.name)
         if isinstance(decl, declarations.Typedef):
            self.class_ = self.GetDeclaration(decl.type.FullName())
            if not self.info.rename:
               self.info.rename = decl.name
         else:
            self.class_ = decl
         self.class_ = copy.deepcopy(self.class_)
         self.all_bases = self.getAllClassBases()

         # Set up the Cheetah template file names.
         base_fname = self.class_.getCleanName()
         self.cxx_adapter_output_file = base_fname + '_Adapter.h'
         self.c_wrapper_output_file = base_fname + '.cpp'
         self.csharp_output_file = base_fname + '.cs'
      else:
         self.class_ = None
         self.c_wrapper_output_file = 'yikes.cpp'
         self.csharp_output_file = 'yikes.cs'

   def getAllClassBases(self):
      '''
      Returns all the base classes of self without taking into account
      hierarchy or which base classes are (or are not) being exported.
      '''
      all_bases = []       
      for level in self.class_.hierarchy:
         for base in level:
            all_bases.append(base)
      return all_bases

   def getImmediateClassBases(self, exportedNames):
      '''
      Returns only the immediate base classes (if any) of self that are
      being exported.
      '''
      bases = []
      exported = False
      for level in self.class_.hierarchy:
         for b in level:
            if b.visibility == declarations.Scope.public and b.FullName() in exportedNames:
               bases.append(b)
               exported = True
         if exported:
            break
      return bases

   def Order(self):
      '''
      Return the TOTAL number of bases that this class has, including the
      bases' bases.  Do this because base classes must be instantialized
      before the derived classes in the module definition.  
      '''
      num_bases = len(self.ClassBases())
      return num_bases, self.class_.FullName()

   def __printDot(self):
      print "\b.",
      sys.__stdout__.flush()

   def Export(self, exported_names):
      self.InheritMethods(exported_names)
      self.MakeNonVirtual()
      if not self.info.exclude:
         self.ExportBasics()
         self.ExportBases(exported_names)
         self.ExportConstructors()
         self.ExportMethods()
         self.ExportVirtualMethods()
         self.exportCallbacks(exported_names)
         self.ExportOperators()
         self.ExportNestedClasses(exported_names)
         self.ExportNestedEnums(exported_names)
         self.ExportSmartPointer()
         self.ExportOpaquePointerPolicies()
         self.exportDataMembers()

         exported_names[self.Name()] = 1

   def Write(self):
      if not self.info.exclude:
         # Set up the mapping information for the templates.
         self.c_wrapper_template.exp_class = self
         self.c_wrapper_template.module    = self.module_bridge
         self.csharp_template.exp_class    = self
         self.csharp_template.module       = self.module_bridge

         c_wrapper_out = os.path.join(self.cxx_dir, self.c_wrapper_output_file)
         csharp_out = os.path.join(self.csharp_dir, self.csharp_output_file)

         # Execute the templates.
         if self.needsAdapter():
            self.cxx_adapter_template.exp_class = self
            self.cxx_adapter_template.module    = self.module_bridge
            self.cxx_adapter_template.includes  = copy.copy(self.includes)
            cxx_adapter_out = os.path.join(self.cxx_dir, self.cxx_adapter_output_file)

            # The C wrapper template will need to know about the adapter
            # header.
            self.includes.append(self.cxx_adapter_output_file)

            try:
               print "\t[C++ Adapter] ",
               sys.__stdout__.flush()
               cxx_file = open(cxx_adapter_out, 'w')
               self.__printDot()
               cxx_file.write(str(self.cxx_adapter_template))
               self.__printDot()
               cxx_file.close()
               print "Done"
            except IOError, (errno, strerror):
               print "I/O error (%s) [%s]: %s" % (errno, cxx_adapter_out, strerror)

         try:
            print "\t[C Wrappers] ",
            sys.__stdout__.flush()
            cxx_file = open(c_wrapper_out, 'w')
            self.__printDot()
            cxx_file.write(str(self.c_wrapper_template))
            self.__printDot()
            cxx_file.close()
            print "Done"
         except IOError, (errno, strerror):
            print "I/O error (%s) [%s]: %s" % (errno, c_wrapper_out, strerror)

         try:
            print "\t[C#] ",
            sys.__stdout__.flush()
            csharp_file = open(csharp_out, 'w')
            self.__printDot()
            csharp_file.write(str(self.csharp_template))
            self.__printDot()
            csharp_file.close()
            print "Done"
         except IOError, (errno, strerror):
            print "I/O error (%s) [%s]: %s" % (errno, csharp_out, strerror)

   def InheritMethods(self, exported_names):
      '''
      Go up in the class hierarchy looking for classes that were not
      exported yet, and then add their public members to this classes
      members, as if they were members of this class. This allows the user to
      just export one type and automatically get all the members from the
      base classes.
      '''
      valid_members = (declarations.Method, declarations.ClassVariable,
                       declarations.NestedClass, declarations.ClassEnumeration)
         # these don't work INVESTIGATE!: (declarations.ClassOperator, declarations.ConverterOperator)
      fullnames = [x.FullName() for x in self.class_]

      # Convert fullnames into a dictionary for easier lookup.
      fullnames = dict([(x, None) for x in fullnames])

      for level in self.class_.hierarchy:
         level_exported = False
         for base in level:
            base = self.GetDeclaration(base.FullName())

            # If base is not named in exported_names, it has not been exported.
            if base.FullName() not in exported_names:
               for member in base:
                  if type(member) in valid_members:
                     member_copy = copy.deepcopy(member)   
                     member_copy.class_ = self.class_.getFullNameAbstract()
                     member_info = self.info[member_copy.name[0]]
                     if not member_info.exclude:
                        if not isinstance(member_copy, declarations.Method) and \
                           member_copy.FullName() not in fullnames:
                           self.class_.AddMember(member)        
            # This base class has been exported.
            else:
               level_exported = True

         if level_exported:
            break

      def IsValid(member):
         return isinstance(member, valid_members) and \
                member.visibility == declarations.Scope.public

      self.public_members = [x for x in self.class_ if IsValid(x)]

   def ExportBasics(self):
      '''Export the name of the class and its class_ statement.'''
      pass

   def ExportBases(self, exportedNames):
      'Expose the bases of this class.'
      self.bases = self.getImmediateClassBases(exportedNames)

   def ExportConstructors(self):
      '''
      Exports all the public contructors of the class, plus indicates if the 
      class is noncopyable.
      '''
      constructors = [x for x in self.public_members if isinstance(x, declarations.Constructor)]

      # don't export the copy constructor if the class is 
      if self.class_.abstract:
         for cons in constructors:
            if cons.IsCopy():
               constructors.remove(cons)
               break

      self.constructors = constructors[:]

      # At this point, if we have no constructors left, then this class
      # cannot be instantiated.
      if not constructors:
         # declare no_init
         self.no_init = True

      # Check if the class is copyable.
      if not self.class_.HasCopyConstructor() or self.class_.abstract:
         self.non_copyable = True

   def OverloadName(self, method):
      'Returns the name of the overloads struct for the given method'
      name = utils.makeid(method.FullName())
      overloads = '_overloads_%i_%i' % (method.minArgs, method.maxArgs)    
      return name + overloads

    
   def GetAddedMethods(self):
      added_methods = self.info.__added__
      result = []
      if added_methods:
         for name, rename in added_methods:
            decl = self.GetDeclaration(name)
            self.info[name].rename = rename
            result.append(decl)
      return result

   def ExportMethods(self):
      '''
      Export all the non-virtual methods of this class, plus any function
      that is to be exported as a method.
      '''
      def canExport(m, hasVirtuals):
         'Returns true if the given method is exportable by this routine'
         ignore = (declarations.Constructor, declarations.ClassOperator,
                   declarations.Destructor)
         method_info = self.info[m.name[0]]

         # A member can be exported as a method if all of the following are
         # true:
         #
         #    * It is not excluded
         #    * It is a function
         #    * It is not an ignored function type (see above)
         #    * It is not private
         #
         # and if any one of the following is true:
         #
         #    * It is a public method
         #    * It is a virtual method
         #    * This class has virtual methods
         return not method_info.exclude and \
                isinstance(m, declarations.Function) and \
                not isinstance(m, ignore) and \
                m.visibility != declarations.Scope.private and \
                (m.virtual or hasVirtuals or \
                 m.visibility == declarations.Scope.public)

      # Determine if this class has non-private virtual methods.
      has_virtuals = False
      for m in self.class_:
         if isinstance(m, declarations.Function) and m.virtual \
            and m.visibility != declarations.Scope.private:
            has_virtuals = True
            break

      # Collect all the exportable methods.
      methods = [x for x in self.class_ if canExport(x, has_virtuals)]
      methods.extend(self.GetAddedMethods())

      for member in methods:
         found = False

         # XXX: This is a very slow way to figure out if a method is
         # overriding a base class method.  If gccxml would tell us
         # when a method is an override, this code would be obsoleted.
         for b in self.all_bases:
            for base_mem in b.getMembers():
               # The second clause of this conditional is needed for
               # those cases when a method is "inherited" from a base
               # class that is not being exported.
               # XXX: This does not take method signatures into account.
#                  member.parameters == base_mem.parameters and \
               if member.name == base_mem.name and \
                  member.FullName() != base_mem.FullName():
                  member.override = True
                  found = True
                  break

            if found:
               break

         if member.virtual:
            self.virtual_methods.append(member)
         elif member.static:
            self.static_methods.append(member)
            if member.visibility == declarations.Scope.protected:
               self.protected_static_methods.append(member)
         else:
            self.non_virtual_methods.append(member)
            if member.visibility == declarations.Scope.protected:
               self.protected_non_virtual_methods.append(member)

      self.export_methods_run = True

   def MakeNonVirtual(self):
      '''
      Make all methods that the user indicated to no_override no more
      virtual, delegating their export to the ExportMethods routine.
      '''
      for member in self.class_:
         if type(member) == declarations.Method and member.virtual:
            member.virtual = not self.info[member.FullName()].no_override 

   def needsAdapter(self):
      exports_protected_methods = False
      for m in self.non_virtual_methods + self.static_methods:
         if m.visibility == declarations.Scope.protected:
            exports_protected_methods = True
            break

      result = self.hasVirtualMethods() or exports_protected_methods

      # The first time we determine that self needs an adapter, that condition
      # will not change.  We "optimize out" this method by storing the result
      # of the above computations for any future calls.
      self.needsAdapter = lambda x = result: x

      return result

   def overloadsEquality(self):
      'Determines whether the wrapped C++ class overloads operator==.'
      result = False
      for o in self.member_operators:
         if o.name[0] == '==':
            result = True
            break
      self.overloadsEquality = lambda x = result: x
      return result

   def hasVirtualMethods(self):
      assert(self.export_methods_run == True,
             "hasVirtualMethods() called too early")

      # Check to see if this class has any virtual methods.
      for member in self.class_:
         if type(member) == declarations.Method and member.virtual:
            return True

      return False

   def hasNonVirtualMethods(self):
      assert(self.export_methods_run == True,
             "hasNonVirtualMethods() called too early")

      # Check to see if this class has any non-virtual, non-static methods.
      for member in self.class_:
         if type(member) == declarations.Method and not member.virtual and \
            not member.static:
            return True

      return False

   def hasStaticMethods(self):
      assert(self.export_methods_run == True,
             "hasStaticMethods() called too early")

      # Check to see if this class has any static methods.
      for member in self.class_:
         if type(member) == declarations.Method and member.static:
            return True

      return False

   def hasStaticData(self):
      # Check to see if this class has any static data members.
      for member in self.class_:
         if type(member) == declarations.ClassVariable and member.static:
            return True

      return False

   def hasDestructor(self):
      # Check to see if this class has a public destructor.
      for member in self.class_:
         if type(member) == declarations.Destructor and member.visibility == declarations.Scope.public:
            return True

      return False

   def ExportVirtualMethods(self):
      holder = self.info.holder
      if holder:
         assert(False)
#         self.Add('template', holder(self.class_.FullName()))

   def exportCallbacks(self, exportedNames):

      def isInheritedVirtual(decl, methodNames):
         return type(decl) == declarations.Method and \
                decl.virtual and decl.name[0] not in methodNames

#      method_names = [x.name[0] for x in self.class_ if type(x) == declarations.Method]
      method_names = [x.name[0] for x in self.virtual_methods]

      # Collect all virtual methods that are inherited (not overridden) into
      # self.inherited_virtual_methods.
      for level in self.class_.hierarchy:
         level_exported = False
         for base in level:
            base = self.GetDeclaration(base.FullName())

            for member in base:
               member_info = self.info[member.name[0]]
               if not member_info.exclude and isInheritedVirtual(member, method_names):
                  self.inherited_virtual_methods.append(member)
                  self.virtual_method_callbacks.append(member)

            if base.FullName() in exportedNames:
               level_exported = True

         if level_exported:
            break

      # Collect virtual methods that are newly introduced by this class
      # directly.  Inherited virtual methods will already have been handled at
      # this point, so we can safely ignore methods that are overrides.
      for method in self.virtual_methods:
         self.virtual_method_callbacks.append(method)

   # Operators natively supported by C#.  This list comes from page 46 of
   # /C# Essentials/, Second Edition.
   CSHARP_SUPPORTED_OPERATORS = '+ - ! ~ ++ -- * / % & | ^ << >>  != > < ' \
                                '>= <= =='.split()

   # Create a map for faster lookup.
   CSHARP_SUPPORTED_OPERATORS = dict(zip(CSHARP_SUPPORTED_OPERATORS,
                                     range(len(CSHARP_SUPPORTED_OPERATORS))))

#   # A dictionary of operators that are not directly supported by boost, but
#   # can be exposed simply as a function with a special name.
#   CSHARP_RENAME_OPERATORS = {
#       '()' : '__call__',
#   }
#
   # converters which have a special name in python
   # it's a map of a regular expression of the converter's result to the
   # appropriate python name
   SPECIAL_CONVERTERS = {
      re.compile(r'(const)?\s*double$') : '__float__',
      re.compile(r'(const)?\s*float$') : '__float__',
      re.compile(r'(const)?\s*int$') : '__int__',
      re.compile(r'(const)?\s*long$') : '__long__',
      re.compile(r'(const)?\s*char\s*\*?$') : 'ToString()',
      re.compile(r'(const)?.*::basic_string<.*>\s*(\*|\&)?$') : 'ToString()',
   }

   def ExportOperators(self):
      'Export all member operators and free operators related to this class'

      def ConverterMethodName(converter):
         result_fullname = converter.result.FullName()
         result_name = converter.result.name
         for regex, method_name in self.SPECIAL_CONVERTERS.items():
            if regex.match(result_fullname):
               return method_name
         else:
            # extract the last name from the full name
            result_name = utils.makeid(result_name)
            return 'to_' + result_name

      def GetFreeOperators():
         'Get all the free (global) operators related to this class'
         operators = []
         for decl in self.declarations:
            if isinstance(decl, declarations.Operator):
               # check if one of the params is this class
               for param in decl.parameters:
                  if param[0].getCPlusPlusName() == self.class_.FullName():
                     operators.append(decl)
                     break
         return operators

      # Handle converter operators first.
#      converters = [x for x in self.public_members if type(x) == declarations.ConverterOperator]
#
#      for converter in converters:
#         info = self.info['operator'][converter.result.FullName()]
#         # check if this operator should be excluded
#         if info.exclude:
#            continue
#
#         special_code = HandleSpecialOperator(converter)
#         if info.rename or not special_code:
#            # export as method
#            name = info.rename or ConverterMethodName(converter)
#            pointer = converter.PointerDeclaration()
#            policy_code = ''
#            if info.policy:
#               policy_code = ', %s()' % info.policy.Code()
#            self.Add('inside', '.def("%s", %s%s)' % (name, pointer, policy_code))
#
#         elif special_code:
#            self.Add('inside', special_code)

      # Now handle free operators and member operators.
      frees = GetFreeOperators()
      members = [x for x in self.public_members if type(x) == declarations.ClassOperator]
      all_operators = frees + members
      operators = [x for x in all_operators if not self.info['operator'][x.FullName()].exclude]

      for operator in all_operators:
         if operator.name[0] not in self.CSHARP_SUPPORTED_OPERATORS:
            continue

         # Gather information about the operator, for use later.
#         wrapper = self.info['operator'][operator.name].wrapper
#         rename = self.info['operator'][operator.FullName()].rename

         # Check if this operator will be exported as a method.
         if isinstance(operator, declarations.ClassOperator):
            result_name = operator.result.getCPlusPlusName()
            param1_name = ''
            if operator.parameters:
               param1_name = operator.parameters[0][0].getCPlusPlusName()

            # check for str
            ostream = 'basic_ostream'
            is_str = result_name.find(ostream) != -1 and param1_name.find(ostream) != -1

            self.member_operators.append(operator)
#            # Export this operator as a normal method, renaming or using
#            # the given wrapper
#            if not rename:
#               if wrapper:
#                  rename = wrapper.name
##               else:
##                  rename = self.CSHARP_RENAME_OPERATORS[operator.name]
         else:
            result_name = operator.result.getCPlusPlusName()
            param1_name = operator.parameters[0][0].getCPlusPlusName()
            param2_name = operator.parameters[1][0].getCPlusPlusName()

            # check for str
            ostream = 'basic_ostream'
            is_str = result_name.find(ostream) != -1 and \
                     (param1_name.find(ostream) != -1 or \
                      param2_name.find(ostream) != -1)

            if not is_str:
               self.global_operators.append(operator)

   def ExportNestedClasses(self, exported_names):
      nested_classes = [x for x in self.public_members if isinstance(x, declarations.NestedClass)]
      for nested_class in nested_classes:
         nested_info = self.info[nested_class.FullName()]
#         print nested_info.exclude
         if not nested_info.exclude:
            nested_info.include = self.info.include
            nested_info.name = nested_class.FullName()
            nested_info.module = self.module
            exporter = ReferenceTypeExporter(nested_info)
            exporter.SetDeclarations(self.declarations)
            exporter.Export(exported_names)
            self.nested_classes.append(exporter)

   def ExportNestedEnums(self, exported_names):
      nested_enums = [x for x in self.public_members if isinstance(x, declarations.ClassEnumeration)]
      for enum in nested_enums:
         enum_info = self.info[enum.name[0]]
         if not enum_info.exclude:
            enum_info.include = self.info.include
            enum_info.name = enum.FullName()
            enum_info.module = self.module
            exporter = EnumExporter.EnumExporter(enum_info)
            exporter.SetDeclarations(self.declarations)
            exporter.Export(exported_names)
            self.nested_enums.append(exporter)

   def ExportSmartPointer(self):
      self.smart_ptr = self.info.smart_ptr

   def ExportOpaquePointerPolicies(self):
      # check all methods for 'return_opaque_pointer' policies
      methods = [x for x in self.public_members if isinstance(x, declarations.Method)]
      for method in methods:
         return_opaque_policy = policies.return_value_policy(policies.return_opaque_pointer)
         if self.info[method.FullName()].policy == return_opaque_policy:
            macro = exporterutils.EspecializeTypeID(method.result.name) 
            if macro:
               self.Add('declaration-outside', macro)

   def exportDataMembers(self):
      def IsExportable(m):
         'Returns true if the given member is exportable by this routine'
         return isinstance(m, declarations.ClassVariable)

      data_members = [x for x in self.public_members if IsExportable(x)]
      for m in data_members:
         if self.info[m.name[0]].exclude:
            continue
         if m.static:
            self.static_members.append(m)
         else:
            self.non_static_members.append(m)
