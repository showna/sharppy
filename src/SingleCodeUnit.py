# This is derived from the Pyste version of SingleCodeUnit.py.
# See http://www.boost.org/ for more information.

from settings import namespaces
import settings
from utils import remove_duplicated_lines, left_equals
from SmartFile import SmartFile


#==============================================================================
# SingleCodeUnit
#==============================================================================
class SingleCodeUnit:
    '''
    Represents a cpp file, where other objects can write in one of the     
    predefined sections.
    The avaiable sections are:
        include - The include area of the cpp file
        declaration - The part before the module definition
        module - Inside the BOOST_PYTHON_MODULE macro
    '''
    
    def __init__(self, modulename, cxx_filename, csharp_filename):
        self.modulename = modulename
        self.cxx_filename = cxx_filename
        self.csharp_filename = csharp_filename
        # define the avaiable C++ sections
        self.cxx_code = {}
        # include section
        self.cxx_code['include'] = '#include "sharppy.h"\n'
        # declaration section (inside namespace)        
        self.cxx_code['declaration'] = ''
        # declaration (outside namespace)
        self.cxx_code['declaration-outside'] = ''
        # inside extern "C"
        self.cxx_code['c-wrappers'] = ''

        # define the avaiable C# sections
        self.csharp_code = {}
        # include section
        self.csharp_code['using'] = 'using System;\nusing System.Runtime.InteropServices;\n'
        # declaration section (inside namespace)        
        self.csharp_code['declaration'] = ''
        # declaration (outside namespace)
        self.csharp_code['declaration-outside'] = ''
        # inside BOOST_PYTHON_MACRO
        self.csharp_code['module'] = ''

        # Create the default C# wrapper definition.
        self.csharp_wrapper_definition = 'namespace %s' % modulename

    def WriteCPlusPlus(self, section, code):
        'write the given code in the section of the C++ code unit'
        if section not in self.cxx_code:
            raise RuntimeError, 'Invalid CodeUnit section: %s' % section
        self.cxx_code[section] += code

    def WriteCSharp(self, section, code):
        'write the given code in the section of the C# code unit'
        if section not in self.csharp_code:
            raise RuntimeError, 'Invalid CodeUnit section: %s' % section
        self.csharp_code[section] += code
        
    def MergeCPlusPlus(self, other):
        for section in ('include', 'declaration', 'declaration-outside', 'c-wrappers'):
            self.cxx_code[section] = self.cxx_code[section] + other.cxx_code[section]    

    def MergeCSharp(self, other):
        for section in ('using', 'declaration', 'declaration-outside', 'module'):
            self.csharp_code[section] = self.csharp_code[section] + other.csharp_code[section]    

    def SectionCPlusPlus(self, section):
        return self.cxx_code[section]

    def SectionCSharp(self, section):
        return self.csharp_code[section]

    def SetCurrent(self, *args):
        pass


    def Current(self):
        pass 

    def Save(self, append=False):
        self.SaveCPlusPlus(append)
        self.SaveCSharp(append)
    
    def _WriteSharppyHeader(self):
        fout = SmartFile('sharppy.h', 'w')
        fout.write('''
#ifndef _SHARPPY_H_
#define _SHARPPY_H_

#ifdef _MSC_VER
#define SHARPPY_API __declspec(dllexport)
#define SHARPPY_CLASS_API __declspec(dllexport)
#else
#define SHARPPY_API
#define SHARPPY_CLASS_API
#endif

#endif /* _SHARPPY_H_ */
''')
        fout.close()

    def SaveCPlusPlus(self, append=False):
        'Writes this code unit to the filename'
        self._WriteSharppyHeader()
        space = '\n\n'
        if not append:
            flag = 'w'
        else:
            flag = 'a'
        fout = SmartFile(self.cxx_filename, flag)
        # includes
        if self.cxx_code['include']:
            includes = remove_duplicated_lines(self.cxx_code['include'])
            fout.write('\n' + left_equals('Includes'))        
            fout.write(includes)
            fout.write(space)

        # declarations
        declaration = self.cxx_code['declaration']
        declaration_outside = self.cxx_code['declaration-outside']
        if declaration_outside or declaration:
            fout.write(left_equals('Declarations'))
            if declaration_outside:
                fout.write(declaration_outside + '\n\n')
            if declaration:
                sharppy_namespace = namespaces.sharppy[:-2]
                fout.write('namespace %s {\n\n' % sharppy_namespace)
                fout.write(declaration) 
                fout.write('\n}// namespace %s\n' % sharppy_namespace)
                fout.write(space)
        # module
        fout.write(left_equals('C Wrapper Functions'))
        fout.write('extern "C"\n')
        fout.write('{\n\n')
        fout.write(self.cxx_code['c-wrappers']) 
        fout.write('}\n')
        fout.close()
    
    def SaveCSharp(self, append=False):
        'Writes this code unit to the filename'
        space = '\n\n'
        if not append:
            flag = 'w'
        else:
            flag = 'a'
        fout = SmartFile(self.csharp_filename, flag)
        # using
        if self.csharp_code['using']:
            includes = remove_duplicated_lines(self.csharp_code['using'])
            fout.write('\n' + left_equals('Using'))
            fout.write(includes)
            fout.write(space)

        # declarations
        declaration = self.csharp_code['declaration']
        declaration_outside = self.csharp_code['declaration-outside']
        if declaration_outside or declaration:
            fout.write(left_equals('Declarations'))
            if declaration_outside:
                fout.write(declaration_outside + '\n\n')
            if declaration:
                sharppy_namespace = namespaces.sharppy[:-2]
                fout.write('namespace %s {\n\n' % sharppy_namespace)
                fout.write(declaration) 
                fout.write('\n}// namespace %s\n' % sharppy_namespace)
                fout.write(space)
        # module
        fout.write(left_equals('Module'))
        fout.write(self.csharp_wrapper_definition + '\n')
        fout.write('{\n')
        fout.write(self.csharp_code['module']) 
        fout.write('}\n\n')
        fout.close()
