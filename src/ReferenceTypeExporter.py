# This is derived from the Pyste version of ClassExporter.py.
# See http://www.boost.org/ for more information.

# For Python 2.1 compatibility.
#from __future__ import nested_scope

import exporters
from Exporter import Exporter
from declarations import *
from settings import *
from policies import *
from EnumExporter import EnumExporter
from utils import makeid, enumerate, generateUniqueName, operatorToString
import copy
import exporterutils
import re

from Cheetah.Template import Template


#==============================================================================
# ReferenceTypeExporter
#==============================================================================
class ReferenceTypeExporter(Exporter):
    'Generates C# P/Invoke bridging code to export a class declaration.'
    
    cxx_template_file    = 'class_cxx.tmpl'
    csharp_template_file = 'class_cs.tmpl'
 
    def __init__(self, info, parser_tail=None):
        Exporter.__init__(self, info, parser_tail)
        self.marshalers = {}

        self.cxx_template = Template(file = self.cxx_template_file)
        self.csharp_template = Template(file = self.csharp_template_file)

        # Abstract data information for the reference type to be exported.
        self.no_init             = False
        self.non_copyable        = False
        self.bases               = []
        self.constructors        = []
        self.non_virtual_methods = []
        self.static_methods      = []
        self.virtual_methods     = []
        self.callback_typedefs   = []

    def getCPlusPlusName(self):
        return '::'.join(self.class_.getFullNameAbstract())

    def getCSharpName(self, withNamespace = True):
        if withNamespace:
            return '.'.join(self.class_.getFullNameAbstract())
        else:
            return '.'.join(self.class_.name)

    def getClassName(self):
        return makeid(self.class_.FullName())

    # The "bridge name" is used for the name of the class that will handle
    # bridging of virtual methods.
    def getBridgeName(self):
        bridge_name = makeid(self.class_.FullName())
        if self.hasVirtualMethods():
            bridge_name += '_bridge'
        return bridge_name

    # The "holder name" is used for the name of the class that will handle
    # smart pointer instances.
    def getHolderName(self):
        return makeid(self.class_.FullName()) + '_holder'

    def Name(self):
        return self.info.name

    def SetDeclarations(self, declarations):
        Exporter.SetDeclarations(self, declarations)
        if self.declarations:
            decl = self.GetDeclaration(self.info.name)
            if isinstance(decl, Typedef):
                self.class_ = self.GetDeclaration(decl.type.name)
                if not self.info.rename:
                    self.info.rename = decl.name
            else:
                self.class_ = decl
            self.class_ = copy.deepcopy(self.class_)
        else:
            self.class_ = None

    def ClassBases(self):
        all_bases = []       
        for level in self.class_.hierarchy:
            for base in level:
                all_bases.append(base)
        return [self.GetDeclaration(x.name) for x in all_bases] 
    
    def Order(self):
        '''Return the TOTAL number of bases that this class has, including the
        bases' bases.  Do this because base classes must be instantialized
        before the derived classes in the module definition.  
        '''
        num_bases = len(self.ClassBases())
        return num_bases, self.class_.FullName()
    
    def Export(self, exported_names):
        self.InheritMethods(exported_names)
        self.MakeNonVirtual()
        if not self.info.exclude:
            self.ExportBasics()
            self.ExportBases(exported_names)
            self.ExportConstructors()
            self.ExportVirtualMethods()
            self.ExportMethods()
            self.ExportVirtualMethodWrappers()
#            self.ExportMethodWrappers()
            self.ExportOperators()
            self.ExportNestedClasses(exported_names)
            self.ExportNestedEnums(exported_names)
            self.ExportSmartPointer()
            self.ExportOpaquePointerPolicies()

            # Set up the mapping information for the templates.
            self.cxx_template.exp_class     = self
            self.cxx_template.module        = self.module
            self.csharp_template.exp_class  = self
            self.csharp_template.marshalers = self.marshalers
            self.csharp_template.module     = self.module

            # Execute the templates.
            print self.cxx_template
            print self.csharp_template

            exported_names[self.Name()] = 1


    def InheritMethods(self, exported_names):
        '''Go up in the class hierarchy looking for classes that were not
        exported yet, and then add their public members to this classes
        members, as if they were members of this class. This allows the user to
        just export one type and automatically get all the members from the
        base classes.
        '''
        valid_members = (Method, ClassVariable, NestedClass, ClassEnumeration)
            # these don't work INVESTIGATE!: (ClassOperator, ConverterOperator)
        fullnames = [x.FullName() for x in self.class_]
        pointers = [x.PointerDeclaration(True) for x in self.class_ if isinstance(x, Method)]
        fullnames = dict([(x, None) for x in fullnames])
        pointers = dict([(x, None) for x in pointers])
        for level in self.class_.hierarchy:
            level_exported = False
            for base in level:
                base = self.GetDeclaration(base.name)
                if base.FullName() not in exported_names:
                    for member in base:
                        if type(member) in valid_members:
                            member_copy = copy.deepcopy(member)   
                            member_copy.class_ = self.class_.getFullNameAbstract()
                            if isinstance(member_copy, Method):
                                pointer = member_copy.PointerDeclaration(True)
                                if pointer not in pointers:
                                    self.class_.AddMember(member)
                                    pointers[pointer] = None
                            elif member_copy.FullName() not in fullnames:
                                self.class_.AddMember(member)        
                else:
                    level_exported = True
            if level_exported:
                break
        def IsValid(member):
            return isinstance(member, valid_members) and member.visibility == Scope.public
        self.public_members = [x for x in self.class_ if IsValid(x)] 

    def WriteOperatorsCPlusPlus(self, indent, wrapperClassName, wrapperClassType):
        'Export all member operators and free operators related to this class'

        def GetFreeOperators():
            'Get all the free (global) operators related to this class'
            operators = []
            for decl in self.declarations:
                if isinstance(decl, Operator):
                    # check if one of the params is this class
                    for param in decl.parameters:
                        if param.name == self.class_.FullName():
                            operators.append(decl)
                            break
            return operators

        def GetOperand(param):
            'Returns the operand of this parameter (either "self", or "other<type>")'
            if param.name == self.class_.FullName():
                return 'self'
            else:
                return ('other< %s >()' % param.name)

        def HandleSpecialOperator(operator):
            # Gather information about the operator and its parameters.
            result_name = operator.result.name                        
            param1_name = ''
            if operator.parameters:
                param1_name = operator.parameters[0].name

            # check for str
            ostream = 'basic_ostream'
            is_str = result_name.find(ostream) != -1 and param1_name.find(ostream) != -1
            if is_str:
                sstream_inc = '#include <sstream>\n'
                if sstream_inc not in self.sections['include']:
                   self.sections['include'].append(sstream_inc)

                code = 'char* %s_ToString(%s* self_)\n' % \
                       (wrapperClassName, wrapperClassType)
                code += '{\n'
                code += indent + "std::ostringstream text;\n"
                code += indent + "text << *self_;\n"
                code += indent + "return text.str().c_str();\n"
                code += '}\n\n'
                return code

            # is not a special operator
            return None

        frees = GetFreeOperators()
        members = [x for x in self.public_members if type(x) == ClassOperator]
        all_operators = frees + members
        operators = [x for x in all_operators if not self.info['operator'][x.name].exclude]
        
        code = ''

        for operator in operators:
            # gatter information about the operator, for use later
            wrapper = self.info['operator'][operator.name].wrapper
            if wrapper:
                pointer = '&' + wrapper.FullName()
                if wrapper.code:
                    self.Add('declaration', wrapper.code)
            else:
                pointer = operator.PointerDeclaration()                 
            rename = self.info['operator'][operator.name].rename

            # Check if this operator will be exported as a method.
#            export_as_method = wrapper or rename or operator.name in self.CSHARP_SUPPORTED_OPERATORS
            export_as_method = False

            # check if this operator has a special representation in boost
            special_code = HandleSpecialOperator(operator)
            has_special_representation = special_code is not None

            if export_as_method:
                # Export this operator as a normal method, renaming or using
                # the given wrapper
                if not rename:
                    if wrapper:
                        rename = wrapper.name
#                    else:
#                        rename = self.CSHARP_RENAME_OPERATORS[operator.name]
                policy = ''
                policy_obj = self.info['operator'][operator.name].policy
                if policy_obj:
                    policy = ', %s()' % policy_obj.Code() 
                self.Add('inside', '.def("%s", %s%s)' % (rename, pointer, policy))
            
            elif has_special_representation:
                code += special_code
                
            elif operator.name in self.CSHARP_SUPPORTED_OPERATORS:
                # export this operator using boost's facilities
                op = operator
                is_unary = isinstance(op, Operator) and len(op.parameters) == 1 or\
                           isinstance(op, ClassOperator) and len(op.parameters) == 0

                c_wrapper_name = "%s_%s" % \
                                 (wrapperClassName, operatorToString(operator.name, is_unary))
                return_type = 'bool'
                param_list  = ''
                op_call     = ''

                # Unary operator.
                if is_unary:
                    param_list = "%s* p0" % wrapperClassType
                    op_call    = "%s(*p0)" % op.name
#                    self.Add('inside', '.def( %sself )' % \
#                        (operator.name))
                # Binary operator.
                else:
                    param_list = "%s* p0, %s* p1" % (wrapperClassType, wrapperClassType)
                    op_call    = "*p0 %s *p1" % op.name
#                    if len(operator.parameters) == 2:
#                        left_operand = GetOperand(operator.parameters[0])
#                        right_operand = GetOperand(operator.parameters[1])
#                    else:
#                        left_operand = 'self'
#                        right_operand = GetOperand(operator.parameters[0])
#                    self.Add('inside', '.def( %s %s %s )' % \
#                        (left_operand, operator.name, right_operand))

                code += 'SHARPPY_API %s %s(%s)\n' % \
                        (return_type, c_wrapper_name, param_list)
                code += '{\n'
                code += indent + 'return %s;\n' % op_call
                code += '}\n\n'

        return code

    def ExportBasics(self):
        '''Export the name of the class and its class_ statement.'''
        self.bridge_name = self.getBridgeName()

    def ExportBases(self, exported_names):
        'Expose the bases of the class into the template section'        
        hierarchy = self.class_.hierarchy
        exported = []
        for level in hierarchy:
            for base in level:
                if base.visibility == Scope.public and base.name in exported_names:
                    exported.append(base.name)
            if exported:
                break
        if exported:
            code = 'bases< %s > ' %  (', '.join(exported))
#            self.Add('template', code)

    def ExportConstructors(self):
        '''
        Exports all the public contructors of the class, plus indicates if the 
        class is noncopyable.
        '''
        constructors = [x for x in self.public_members if isinstance(x, Constructor)]

        # don't export the copy constructor if the class is abstract
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
        name = makeid(method.FullName())
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
        '''Export all the non-virtual methods of this class, plus any function
        that is to be exported as a method'''
            
        declared = {}
        def DeclareOverloads(m):
            'Declares the macro for the generation of the overloads'
            if (isinstance(m, Method) and m.static) or type(m) == Function:
                func = m.FullName()
                macro = 'BOOST_PYTHON_FUNCTION_OVERLOADS'
            else:
                func = m.name
                macro = 'BOOST_PYTHON_MEMBER_FUNCTION_OVERLOADS' 
            code = '%s(%s, %s, %i, %i)\n' % (macro, self.OverloadName(m), func, m.minArgs, m.maxArgs)
            if code not in declared:
                declared[code] = True
                self.Add('declaration', code)


        def Pointer(m):
            'returns the correct pointer declaration for the method m'
            # check if this method has a wrapper set for him
            wrapper = self.info[m.name].wrapper
            if wrapper:
                return '&' + wrapper.FullName()
            else:
                return m.PointerDeclaration() 

        def IsExportable(m):
            'Returns true if the given method is exportable by this routine'
            ignore = (Constructor, ClassOperator, Destructor)
            return isinstance(m, Function) and not isinstance(m, ignore) and not m.virtual        

        methods = [x for x in self.public_members if IsExportable(x)]
        methods.extend(self.GetAddedMethods())

        for m in methods:
            if m.static:
                self.static_methods.append(m)
            else:
                self.non_virtual_methods.append(m)

    def MakeNonVirtual(self):
        '''Make all methods that the user indicated to no_override no more
        virtual, delegating their export to the ExportMethods routine'''
        for member in self.class_:
            if type(member) == Method and member.virtual:
                member.virtual = not self.info[member.FullName()].no_override 

    def hasVirtualMethods(self):
        # Check to see if this class has any virtual methods.
        for member in self.class_:
            if type(member) == Method and member.virtual:
                return True

        return False

    def hasDestructor(self):
        # Check to see if this class has a public destructor.
        for member in self.class_:
            if type(member) == Destructor and member.visibility == 'public':
                return True

        return False

    def ExportVirtualMethods(self):        
        holder = self.info.holder
        self.virtual_methods = []
        if self.hasVirtualMethods():
            self.bases = [self.class_]
            for member in self.class_:
                if type(member) == Method and member.virtual:
                    self.virtual_methods.append(member)
#            if holder:
#                self.Add('template', holder(self.wrapper_generator.FullName()))
#            else:
#                self.Add('template', self.wrapper_generator.FullName())
#            for definition in self.wrapper_generator.GenerateDefinitions():
#                self.Add('inside', definition)
        else:
            if holder:
                assert(False)
#                self.Add('template', holder(self.class_.FullName()))

    def ExportVirtualMethodWrappers(self):
        pass
#        if self.hasVirtualMethods():
#            self.callback_typedefs = self.wrapper_generator.callback_typedefs

    # Operators natively supported by C#.  This list comes from page 46 of
    # /C# Essentials/, Second Edition.
    CSHARP_SUPPORTED_OPERATORS = '+ - ! ~ ++ -- * / % & | ^ << >>  != > < ' \
                                 '>= <= =='.split()

    # Create a map for faster lookup.
    CSHARP_SUPPORTED_OPERATORS = dict(zip(CSHARP_SUPPORTED_OPERATORS,
                                      range(len(CSHARP_SUPPORTED_OPERATORS))))

#    # A dictionary of operators that are not directly supported by boost, but
#    # can be exposed simply as a function with a special name.
#    CSHARP_RENAME_OPERATORS = {
#        '()' : '__call__',
#    }
#
#    # converters which have a special name in python
#    # it's a map of a regular expression of the converter's result to the
#    # appropriate python name
#    SPECIAL_CONVERTERS = {
#        re.compile(r'(const)?\s*double$') : '__float__',
#        re.compile(r'(const)?\s*float$') : '__float__',
#        re.compile(r'(const)?\s*int$') : '__int__',
#        re.compile(r'(const)?\s*long$') : '__long__',
#        re.compile(r'(const)?\s*char\s*\*?$') : '__str__',
#        re.compile(r'(const)?.*::basic_string<.*>\s*(\*|\&)?$') : '__str__',
#    }
        
    def ExportOperators(self):
        'Export all member operators and free operators related to this class'
        
        # export the converters.
        # export them as simple functions with a pre-determined name

        converters = [x for x in self.public_members if type(x) == ConverterOperator]
                
        def ConverterMethodName(converter):
            result_fullname = converter.result.FullName()
            result_name = converter.result.name
            for regex, method_name in self.SPECIAL_CONVERTERS.items():
                if regex.match(result_fullname):
                    return method_name
            else:
                # extract the last name from the full name
                result_name = makeid(result_name)
                return 'to_' + result_name
            
        for converter in converters:
            info = self.info['operator'][converter.result.FullName()]
            # check if this operator should be excluded
            if info.exclude:
                continue
            
            special_code = HandleSpecialOperator(converter)
            if info.rename or not special_code:
                # export as method
                name = info.rename or ConverterMethodName(converter)
                pointer = converter.PointerDeclaration()
                policy_code = ''
                if info.policy:
                    policy_code = ', %s()' % info.policy.Code()
                self.Add('inside', '.def("%s", %s%s)' % (name, pointer, policy_code))
                    
            elif special_code:
                self.Add('inside', special_code)



    def ExportNestedClasses(self, exported_names):
        nested_classes = [x for x in self.public_members if isinstance(x, NestedClass)]
        for nested_class in nested_classes:
            nested_info = self.info[nested_class.FullName()]
            nested_info.include = self.info.include
            nested_info.name = nested_class.FullName()
            exporter = ReferenceTypeExporter(nested_info)
            exporter.SetDeclarations(self.declarations)
            exporter.Export(exported_names)

    def ExportNestedEnums(self, exported_names):
        nested_enums = [x for x in self.public_members if isinstance(x, ClassEnumeration)]
        for enum in nested_enums:
            enum_info = self.info[enum.name]
            enum_info.include = self.info.include
            enum_info.name = enum.FullName()
            exporter = EnumExporter(enum_info)
            exporter.SetDeclarations(self.declarations)
            # XXX: This can't possibly be done yet...
            assert(False)
            exporter.Export(exported_names)


    def ExportSmartPointer(self):
        smart_ptr = self.info.smart_ptr
        if smart_ptr:
            class_name = self.class_.FullName()
            smart_ptr = smart_ptr % class_name
            self.Add('scope', 'register_ptr_to_python< %s >();' % (smart_ptr))
            

    def ExportOpaquePointerPolicies(self):
        # check all methods for 'return_opaque_pointer' policies
        methods = [x for x in self.public_members if isinstance(x, Method)]
        for method in methods:
            return_opaque_policy = return_value_policy(return_opaque_pointer)
            if self.info[method.FullName()].policy == return_opaque_policy:
                macro = exporterutils.EspecializeTypeID(method.result.name) 
                if macro:
                    self.Add('declaration-outside', macro)
