# This is derived from the Pyste version of infos.py.
# See http://www.boost.org/ for more information.

import os.path
import copy
import re
import exporters 
import ReferenceTypeExporter
import ValueTypeExporter
import FreeTypesExporter
#import HeaderExporter
import VarExporter
import CodeExporter
import exporterutils
import utils
import declarations


#==============================================================================
# DeclarationInfo
#==============================================================================
class DeclarationInfo:
    
    def __init__(self, otherInfo=None):
        self.__infos = {}
        self.__attributes = {}
        if otherInfo is not None:
            self.__infos = copy.deepcopy(otherInfo.__infos)
            self.__attributes = copy.deepcopy(otherInfo.__attributes)


    def __getitem__(self, name):
        'Used to access sub-infos'        
        if name.startswith('__'):
            raise AttributeError
        default = DeclarationInfo()
        default._Attribute('name', name)
        return self.__infos.setdefault(name, default)


    def __getattr__(self, name):
        return self[name]


    def _Attribute(self, name, value=None):
        if value is None:
            # get value
            return self.__attributes.get(name)
        else:
            # set value
            self.__attributes[name] = value

#==============================================================================
# FreeTypesHolderInfo
#==============================================================================
class FreeTypesHolderInfo(DeclarationInfo):

    def __init__(self, module, class_, include):
        DeclarationInfo.__init__(self)
        self._Attribute('holder_class', class_)
        self._Attribute('include', include)
        self._Attribute('module', module)
        self._Attribute('funcs', [])
        self._Attribute('enums', [])
        self._Attribute('constants', [])
        exporter = FreeTypesExporter.FreeTypesExporter(InfoWrapper(self))
        if exporter not in exporters.exporters:
            exporters.exporters.append(exporter) 
        exporter.interface_file = exporters.current_interface 

    def addFunction(self, name):
        self._Attribute('funcs').append(name)

    def addEnum(self, name):
        self._Attribute('enums').append(name)

    def addConstant(self, name):
        self._Attribute('constants').append(name)


#==============================================================================
# ReferenceTypeInfo
#==============================================================================
class ReferenceTypeInfo(DeclarationInfo):

    def __init__(self, module, name, include, tail = None, otherInfo = None,
                 extraHeaders = None, rename = None):
        DeclarationInfo.__init__(self, otherInfo)
        if rename:
            declarations.rename_map[name] = rename
            self._Attribute('rename', rename)
        self._Attribute('name', name)
        self._Attribute('include', include)
        if None == extraHeaders:
            extraHeaders = []
        self._Attribute('extra_headers', extraHeaders)
        self._Attribute('exclude', False)
        self._Attribute('module', module)
        # create a ReferenceTypeExporter
        exporter = ReferenceTypeExporter.ReferenceTypeExporter(InfoWrapper(self), tail)
        if exporter not in exporters.exporters:
            exporters.exporters.append(exporter) 
        exporter.interface_file = exporters.current_interface 


#==============================================================================
# ValueTypeInfo
#==============================================================================
class ValueTypeInfo(DeclarationInfo):

    def __init__(self, module, name, include, tail=None, otherInfo=None):
        DeclarationInfo.__init__(self, otherInfo)
        self._Attribute('name', name)
        self._Attribute('include', include)
        self._Attribute('exclude', False)
        self._Attribute('module', module)
        # create a ValueTypeExporter
        exporter = ValueTypeExporter.ValueTypeExporter(InfoWrapper(self), tail)
        if exporter not in exporters.exporters: 
            exporters.exporters.append(exporter) 
        exporter.interface_file = exporters.current_interface 
        

#==============================================================================
# templates
#==============================================================================
def GenerateName(name, type_list):
    name = name.replace('::', '_')
    names = [name] + type_list
    return utils.makeid('_'.join(names))


class ReferenceTypeTemplateInfo(DeclarationInfo):

    def __init__(self, module, name, include):
        DeclarationInfo.__init__(self)
        self._Attribute('name', name)
        self._Attribute('include', include)
        self._Attribute('module', module)

    def Instantiate(self, type_list, headers = None, rename=None):
        if headers is None:
            headers = []

#        if not rename:
#            generic_name = GenerateName(self._Attribute('name'), type_list)
#        else:
#            generic_name = rename
        generic_name = GenerateName(self._Attribute('name'), type_list)

        # generate code to instantiate the template
        types = ', '.join(type_list)
        tail = ''
        for h in headers:
           tail += '#include <%s>\n' % h
        # XXX: I don't think that this should be in the global namespace...
        tail += 'typedef %s< %s > %s;\n' % (self._Attribute('name'), types,
                                            generic_name)
        tail += 'void __instantiate_%s()\n' % generic_name
        tail += '{ sizeof(%s); }\n\n' % generic_name

        name = '%s<%s>' % (self._Attribute('name'), ','.join(type_list))

        # Remove all but the most necessary whitespace from name.
        name = re.sub(r'\s+', '', name)
        # This must be applied twice to catch cases where an odd number of
        # '>' characters are adjacent.
        name = re.sub(r'>>', '> >', name)
        name = re.sub(r'>>', '> >', name)

        # Create a ReferenceTypeInfo using the template instantiation we forced.
        return ReferenceTypeInfo(self._Attribute('module'), name,
                                 self._Attribute('include'), tail, self,
                                 headers, rename)

    def __call__(self, types, headers = None, rename = None):
        if headers is None:
            headers = []

        if isinstance(types, str):
            types = types.split() 
        return self.Instantiate(types, headers, rename)

class ValueTypeTemplateInfo(DeclarationInfo):

    def __init__(self, module, name, include):
        DeclarationInfo.__init__(self)
        self._Attribute('name', name)
        self._Attribute('include', include)
        self._Attribute('module', module)

    def Instantiate(self, type_list, headers = None, rename = None):
        if headers is None:
            headers = []

        if not rename:
            rename = GenerateName(self._Attribute('name'), type_list)
        # generate code to instantiate the template
        types = ', '.join(type_list)
        tail = ''
        for h in headers:
           tail += '#include <%s>\n' % h
        tail += 'typedef %s< %s > %s;\n' % (self._Attribute('name'), types, rename)
        tail += 'void __instantiate_%s()\n' % rename
        tail += '{ sizeof(%s); }\n\n' % rename
        # create a ReferenceTypeInfo.
        class_ = ValueTypeInfo(self._Attribute('module'), rename, self._Attribute('include'), tail, self)
        return class_


    def __call__(self, types, headers = None, rename = None):
        if headers is None:
            headers = []

        if isinstance(types, str):
            types = types.split() 
        return self.Instantiate(types, headers, rename)


#==============================================================================
# HeaderInfo
#==============================================================================
#class HeaderInfo(DeclarationInfo):
#
#    def __init__(self, include):
#        DeclarationInfo.__init__(self)
#        self._Attribute('include', include)
#        exporter = HeaderExporter.HeaderExporter(InfoWrapper(self))
#        if exporter not in exporters.exporters: 
#            exporters.exporters.append(exporter)
#        exporter.interface_file = exporters.current_interface 


#==============================================================================
# VarInfo
#==============================================================================
class VarInfo(DeclarationInfo):
    
    def __init__(self, name, include):
        DeclarationInfo.__init__(self)
        self._Attribute('name', name)
        self._Attribute('include', include)
        exporter = VarExporter.VarExporter(InfoWrapper(self))
        if exporter not in exporters.exporters: 
            exporters.exporters.append(exporter)
        exporter.interface_file = exporters.current_interface 
        
                                 
#==============================================================================
# CodeInfo                                 
#==============================================================================
class CodeInfo(DeclarationInfo):

    def __init__(self, code, section):
        DeclarationInfo.__init__(self)
        self._Attribute('code', code)
        self._Attribute('section', section)
        exporter = CodeExporter.CodeExporter(InfoWrapper(self))
        if exporter not in exporters.exporters:
            exporters.exporters.append(exporter)
        exporter.interface_file = exporters.current_interface
        

#==============================================================================
# InfoWrapper
#==============================================================================
class InfoWrapper:
    'Provides a nicer interface for a info'

    def __init__(self, info):
        self.__dict__['_info'] = info # so __setattr__ is not called

    def __getitem__(self, name):
        return InfoWrapper(self._info[name])

    def __getattr__(self, name):
        return self._info._Attribute(name)

    def __setattr__(self, name, value):
        self._info._Attribute(name, value)


#==============================================================================
# Functions
#==============================================================================
def exclude(info):
    info._Attribute('exclude', True)

def property(info):
    info._Attribute('property', True)

def set_policy(info, policy):
    info._Attribute('policy', policy)

def rename(info, name):
    info._Attribute('rename', name)
    declarations.rename_map[info.name] = name

def set_wrapper(info, wrapper):
    if isinstance(wrapper, str):
        wrapper = exporterUtils.FunctionWrapper(wrapper)
    info._Attribute('wrapper', wrapper)

def instantiate(template, types, rename=None):
    if isinstance(types, str):
        types = types.split()
    return template.Instantiate(types, rename)

def use_smart_ptr(info, decl = None, refCounted = False):
    info._Attribute('smart_ptr', True)
    info._Attribute('ref_counted', refCounted)
    info._Attribute('smart_ptr_decl', decl)

def use_shared_ptr(info):
    info._Attribute('smart_ptr', True)
    info._Attribute('ref_counted', True)
    info._Attribute('smart_ptr_decl', 'boost::shared_ptr< %s >')

def use_auto_ptr(info):
    info._Attribute('smart_ptr', True)
    info._Attribute('ref_counted', True)
    info._Attribute('smart_ptr_decl', 'std::auto_ptr< %s >')

def no_smart_ptr(info):
    info._Attribute('direct_call', True)

def holder(info, function):
    msg = "Expected a callable that accepts one string argument."
    assert callable(function), msg
    info._Attribute('holder', function)

def add_method(info, name, rename=None):
    added = info._Attribute('__added__')
    if added is None:
        info._Attribute('__added__', [(name, rename)])
    else:
        added.append((name, rename))

def sealed(info):
    info._Attribute('sealed', True)
