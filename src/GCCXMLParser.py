# This is derived from the Pyste version of GCCXMLParser.py.
# See http://www.boost.org/ for more information.

import declarations
import elementtree.ElementTree
import xml.parsers.expat
import copy
import re
import utils


#==============================================================================
# Exceptions
#==============================================================================
class InvalidXMLError(Exception): pass

class ParserError(Exception): pass

class InvalidContextError(ParserError): pass


#==============================================================================
# GCCXMLParser
#==============================================================================
class GCCXMLParser(object):
    'Parse a GCC_XML file and extract the top-level declarations.'
    
    interested_tags = {'Class':0, 'Function':0, 'Variable':0, 'Enumeration':0}
    
    def Parse(self, filename):
        self.elements = self.GetElementsFromXML(filename)
        # high level declarations
        self.declarations = []
        self._names = {}
        # parse the elements
        for id in self.elements:
            element, decl = self.elements[id]
            if decl is None: 
                try:
                    self.ParseElement(id, element)
                except InvalidContextError:
                    pass # ignore those nodes with invalid context 
                         # (workaround gccxml bug)
         

    def Declarations(self):
        return self.declarations


    def AddDecl(self, decl):
        if decl.getFullCPlusPlusName() in self._names:
            decl.is_unique= False
            for d in self.declarations:
                if d.getFullCPlusPlusName() == decl.getFullCPlusPlusName():
                    d.is_unique = False
        self._names[decl.getFullCPlusPlusName()] = 0
        self.declarations.append(decl)

        
    def ParseElement(self, id, element):
        method = 'Parse' + element.tag
        if hasattr(self, method):
            func = getattr(self, method)
            func(id, element)
        else:
            self.ParseUnknown(id, element)

            
    def GetElementsFromXML(self,filename):
        'Extracts a dictionary of elements from the gcc_xml file.'
        
        tree = elementtree.ElementTree.ElementTree()
        try:
            tree.parse(filename)
        except xml.parsers.expat.ExpatError:
            raise InvalidXMLError, 'Not an XML file: %s' % filename

        root = tree.getroot()
        if root.tag != 'GCC_XML':
            raise InvalidXMLError, 'Not a valid GCC_XML file'

        # build a dictionary of id -> element, None
        elementlist = root.getchildren()
        elements = {}
        for element in elementlist:
            id = element.get('id')
            if id:
                elements[id] = element, None
        return elements


    def GetDecl(self, id):
        if id not in self.elements:
            if id == '_0':
                raise InvalidContextError, 'Invalid context found in the xml file.'
            else: 
                msg = 'ID not found in elements: %s' % id
                raise ParserError, msg

        elem, decl = self.elements[id]
        if decl is None:
            self.ParseElement(id, elem)
            elem, decl = self.elements[id]
            if decl is None:
                raise ParserError, 'Could not parse element: %s' % elem.tag
        return decl


    def GetType(self, id):
        def Check(id, feature):
            pos = id.find(feature)
            if pos != -1:
                id = id[:pos] + id[pos+1:]
                return True, id
            else:
                return False, id
        const, id = Check(id, 'c')
        volatile, id = Check(id, 'v')
        restricted, id = Check(id, 'r')
        decl = self.GetDecl(id)
        if isinstance(decl, declarations.Type):
            res = copy.deepcopy(decl)
            if const:
                res.const = const
            if volatile: 
                res.volatile = volatile
            if restricted:
                res.restricted = restricted
        else:
            res = declarations.Type(decl, decl.getFullCPlusPlusName(), const)
            res.volatile = volatile
            res.restricted = restricted
        return res            

    def GetLocation(self, location):
        file, line = location.split(':')
        file = self.GetDecl(file)
        return file, int(line)

    def Update(self, id, decl):
        element, _ = self.elements[id]
        self.elements[id] = element, decl

    def ParseUnknown(self, id, element):
        name = '__Unknown_Element_%s' % id
        decl = declarations.Unknown(name)
        self.Update(id, decl)

    def ParseNamespace(self, id, element):
        namespace = element.get('name')
        context = element.get('context')
        if context:
            outer = self.GetDecl(context)
            if not outer.endswith('::'):
                outer += '::'
            namespace = outer + namespace
        if namespace.startswith('::'):
            namespace = namespace[2:]
        self.Update(id, namespace)


    def ParseFile(self, id, element):
        filename = element.get('name')
        self.Update(id, filename)

    def ParseVariable(self, id, element):
        # in gcc_xml, a static Field is declared as a Variable, so we check
        # this and call the Field parser.
        context = self.GetDecl(element.get('context'))
        if isinstance(context, declarations.Class):
            self.ParseField(id, element)
            elem, decl = self.elements[id]
            decl.static = True
        else:
            namespace = context.split('::')
            name = element.get('name')                    
            type_ = self.GetType(element.get('type'))
            location = self.GetLocation(element.get('location'))
            init = element.get('init')
            variable = declarations.Variable(type_, name, namespace, init)
            variable.location = location
            self.AddDecl(variable)
            self.Update(id, variable)
        

    def GetArguments(self, element):
        args = []
        for child in element:
            if child.tag == 'Argument':
                type = self.GetType(child.get('type'))
                type.default = child.get('default')                
                args.append(type)
        return args

    
    def GetExceptions(self, exception_list):
        if exception_list is None:
            return None

        exceptions = []
        for t in exception_list.split():
            exceptions.append(self.GetType(t))

        return exceptions


    def ParseFunction(self, id, element, functionType=declarations.Function):
        '''functionType is used because a Operator is identical to a normal 
        function, only the type of the function changes.'''
        name = element.get('name')
        returns = self.GetType(element.get('returns'))
        namespace = self.GetDecl(element.get('context')).split('::')
        location = self.GetLocation(element.get('location'))
        params = self.GetArguments(element)
        incomplete = bool(int(element.get('incomplete', 0)))
        throws = self.GetExceptions(element.get('throw', None))
        function = functionType(name, namespace, returns, params, throws) 
        function.location = location
        self.AddDecl(function)
        self.Update(id, function)


    def ParseOperatorFunction(self, id, element):
        self.ParseFunction(id, element, declarations.Operator)

        
    def GetHierarchy(self, bases):       
        '''Parses the string "bases" from the xml into a list of tuples of Base
        instances. The first tuple is the most direct inheritance, and then it
        goes up in the hierarchy. 
        '''

        if bases is None:
            return []
        base_names = bases.split()
        this_level = []      
        next_levels = []
        for base in base_names:
            # get the visibility
            split = base.split(':')
            if len(split) == 2:
                visib = split[0]
                base = split[1]
            else:
                visib = declarations.Scope.public                            
            decl = self.GetDecl(base) 
            if not isinstance(decl, declarations.Class):
                # on windows, there are some classes which "bases" points to an
                # "Unimplemented" tag, but we are not interested in this classes
                # anyway
                continue
            base = declarations.Base(decl, visib)
            this_level.append(base)
            # normalize with the other levels
            for index, level in utils.enumerate(decl.hierarchy):
                if index < len(next_levels):
                    next_levels[index] = next_levels[index] + level
                else:
                    next_levels.append(level)
        hierarchy = []
        if this_level:
            hierarchy.append(tuple(this_level))
        if next_levels:
            hierarchy.extend(next_levels)
        return hierarchy

        
    def GetMembers(self, member_list):
        # members must be a string with the ids of the members
        if member_list is None:
            return []
        members = []
        for member in member_list.split():
            decl = self.GetDecl(member)
            if type(decl) in declarations.Class.ValidMemberTypes():
                if type(decl) is str:
                    print decl
                members.append(decl) 
        return members

    def ParseClass(self, id, element):
        cxx_name = element.get('name')
        abstract = bool(int(element.get('abstract', '0')))
        location = self.GetLocation(element.get('location'))
        context = self.GetDecl(element.get('context'))
        incomplete = bool(int(element.get('incomplete', 0)))

        if isinstance(context, str):
            class_ = declarations.Class(cxx_name, context.split('::'),
                                        [], abstract)
        else:
            # a nested class
            visib = element.get('access', declarations.Scope.public)
            class_ = declarations.NestedClass(cxx_name, context.getFullCPlusPlusName(),
                                              visib, [], abstract)
 
        class_.incomplete = incomplete
        # we have to add the declaration of the class before trying        
        # to parse its members and bases, to avoid recursion.
        self.AddDecl(class_)
        class_.location = location
        self.Update(id, class_)       
        # now we can get the members and the bases
        class_.hierarchy = self.GetHierarchy(element.get('bases'))        
        if class_.hierarchy:
            class_.bases = class_.hierarchy[0]
        members = self.GetMembers(element.get('members'))
        for member in members:
            if type(member) is str:
                print member
            class_.AddMember(member)


    def ParseStruct(self, id, element):
        self.ParseClass(id, element)


    def ParseFundamentalType(self, id, element):
        name = element.get('name')
        type_ = declarations.FundamentalType(name)
        self.Update(id, type_)

    type_re = re.compile(r"(_\d+)")

    def ParseArrayType(self, id, element):
        type_attr = element.get('type')
        type = self.GetType(type_attr)

        type_match = self.type_re.match(type_attr)
        if None != type_match:
            decl = self.GetDecl(type_match.group(1))
        else:
            assert(False)

        min = element.get('min')
        max = element.get('max')
        array = declarations.ArrayType(decl, type.getFullCPlusPlusName(),
                                       type.const, min, max)
        self.Update(id, array)

    def ParseReferenceType(self, id, element):
        type_attr = element.get('type')
        type = self.GetType(type_attr)

        type_match = self.type_re.match(type_attr)
        if None != type_match:
            decl = self.GetDecl(type_match.group(1))
        else:
            assert(False)

        expand = not isinstance(type, declarations.FunctionType)
        ref = declarations.ReferenceType(decl, type.getFullCPlusPlusName(), type.const,
                                         None, expand, type.suffix)
        self.Update(id, ref)


    def ParsePointerType(self, id, element):
        type_attr = element.get('type')
        type = self.GetType(type_attr)

        type_match = self.type_re.match(type_attr)
        if None != type_match:
#            print "Looking up declaration for %s (id = %s)" % (type, type_match.group(1))
            decl = self.GetDecl(type_match.group(1))
#            print "\t", decl
        else:
            assert(False)

        expand = not isinstance(type, declarations.FunctionType)
        ref = declarations.PointerType(decl, type.getFullCPlusPlusName(), type.const, None,
                                       expand, type.suffix)
        self.Update(id, ref)


    def ParseFunctionType(self, id, element):
        result = self.GetType(element.get('returns'))
        args = self.GetArguments(element)
        func = declarations.FunctionType(result, args)
        self.Update(id, func)


    def ParseMethodType(self, id, element):
        class_ = self.GetDecl(element.get('basetype')).getFullCPlusPlusName()
        result = self.GetType(element.get('returns'))
        args = self.GetArguments(element)
        method = declarations.MethodType(result, args, class_)
        self.Update(id, method)

        
    def ParseField(self, id, element):
        name = element.get('name')
        visib = element.get('access', declarations.Scope.public)
        classname = self.GetDecl(element.get('context')).getFullCPlusPlusName()
        type_ = self.GetType(element.get('type'))
        static = bool(int(element.get('extern', '0')))
        location = self.GetLocation(element.get('location'))
        var = declarations.ClassVariable(type_, name, classname, visib, static)
        var.location = location
        self.Update(id, var)


    def ParseMethod(self, id, element, methodType=declarations.Method):
        name = element.get('name')
        result = self.GetType(element.get('returns'))
        classname = self.GetDecl(element.get('context')).getFullCPlusPlusName()
        visib = element.get('access', declarations.Scope.public)
        static = bool(int(element.get('static', '0')))
        virtual = bool(int(element.get('virtual', '0')))
        abstract = bool(int(element.get('pure_virtual', '0')))
        const = bool(int(element.get('const', '0')))
        location = self.GetLocation(element.get('location'))
        throws = self.GetExceptions(element.get('throw', None)) 
        params = self.GetArguments(element)
        method = methodType(
            name, classname, result, params, visib, virtual, abstract, static, const, throws)
        method.location = location
        self.Update(id, method)


    def ParseOperatorMethod(self, id, element):
        self.ParseMethod(id, element, declarations.ClassOperator)

        
    def ParseConstructor(self, id, element):
        name = element.get('name')
        visib = element.get('access', declarations.Scope.public)
        classname = self.GetDecl(element.get('context')).getFullCPlusPlusName()
        location = self.GetLocation(element.get('location'))
        params = self.GetArguments(element)
        ctor = declarations.Constructor(name, classname, params, visib)
        ctor.location = location
        self.Update(id, ctor)


    def ParseDestructor(self, id, element):
        name = element.get('name')
        visib = element.get('access', declarations.Scope.public)
        classname = self.GetDecl(element.get('context')).getFullCPlusPlusName()
        virtual = bool(int(element.get('virtual', '0')))
        location = self.GetLocation(element.get('location'))
        des = declarations.Destructor(name, classname, visib, virtual)
        des.location = location
        self.Update(id, des)


    def ParseConverter(self, id, element):
        self.ParseMethod(id, element, declarations.ConverterOperator)


    def ParseTypedef(self, id, element):
        name = element.get('name')
        type = self.GetType(element.get('type'))        
        context = self.GetDecl(element.get('context'))
        if isinstance(context, declarations.Class):
            context = context.getFullCPlusPlusName()
        typedef = declarations.Typedef(type, name, context.split('::'))
        self.Update(id, typedef)
        self.AddDecl(typedef)


    def ParseEnumeration(self, id, element):
        name = element.get('name')
        location = self.GetLocation(element.get('location'))
        context = self.GetDecl(element.get('context'))
        incomplete = bool(int(element.get('incomplete', 0))) 
        if isinstance(context, str):
            enum = declarations.Enumeration(name, context.split('::'))
        else:
            visib = element.get('access', declarations.Scope.public)
            enum = declarations.ClassEnumeration(name, context.getFullCPlusPlusName(),
                                                 visib)
        self.AddDecl(enum)
        enum.location = location
        for child in element:
            if child.tag == 'EnumValue':
                name = child.get('name')
                value = int(child.get('init'))
                enum.values[name] = value
        enum.incomplete = incomplete
        self.Update(id, enum)



def ParseDeclarations(filename):
    'Returns a list of the top declarations found in the gcc_xml file.'
        
    parser = GCCXMLParser() 
    parser.Parse(filename)
    return parser.Declarations()


if __name__ == '__main__':
    ParseDeclarations(r'D:\Programming\Libraries\boost-cvs\boost\libs\python\pyste\example\test.xml')
