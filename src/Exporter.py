# This is derived from the Pyste version of Exporter.py.
# See http://www.boost.org/ for more information.

# $Id: Exporter.py,v 1.9 2003-11-24 20:20:04 patrick Exp $

import os

#==============================================================================
# Exporter
#==============================================================================
class Exporter(object):
   'Base class for objects capable to generate boost.python code.'

   INDENT = ' ' * 3

   def __init__(self, info, parser_tail=None):
      self.info = info
      self.parser_tail = parser_tail
      self.interface_file = None
      self.declarations = []
      self.includes = []
      self.module = info.module
      if self.module == '' or self.module == None:
         # XXX: Come up with a better name for this...
         self.module = 'my_bridge'
      else:
         self.module += '_bridge'
      self.cxx_dir = self.module + '_cpp'
      self.csharp_dir = self.module + '_cs'
      self._createOutputDirs()

   def Name(self):
      raise NotImplementedError(self.__class__.__name__)

   def Tail(self):
      return self.parser_tail

   def Parse(self, parser):
      self.parser = parser
      header = self.info.include
      tail = self.parser_tail
      declarations, parser_header = parser.parse(header, tail)
      self.parser_header = parser_header
      self.SetDeclarations(declarations)

   def SetParsedHeader(self, parsed_header):
      if parsed_header not in self.includes:
         self.includes.append(parsed_header)

   def _createOutputDirs(self):
      cxx    = self.cxx_dir
      csharp = self.csharp_dir

      if os.access(cxx, os.F_OK):
         if not os.access(cxx, os.R_OK):
            # XXX: Need to throw an exception here.
            print 'C++ Crap'
      else:
         os.mkdir(cxx)

      if os.access(csharp, os.F_OK):
         if not os.access(csharp, os.R_OK):
            # XXX: Need to throw an exception here.
            print 'C# Crap'
      else:
         os.mkdir(csharp)

   def SetDeclarations(self, declarations):
      self.declarations = declarations

   def GenerateCode(self, exported_names):
      self.Export(exported_names)
      self.Write()

   def Export(self, exported_names):
      'Subclasses must override this to do the real work.'
      pass

   def Write(self):
      'Subclasses must override this to do the real work.'
      pass

   def GetDeclarations(self, fullname):
      decls = []
      for decl in self.declarations:
         if decl.FullName() == fullname:
            decls.append(decl)
      if not decls:
         raise RuntimeError, 'no %s declaration found!' % fullname
      return decls

   def GetDeclaration(self, fullname):
      decls = self.GetDeclarations(fullname)
      #assert len(decls) == 1
      return decls[0]

   def Order(self):
      '''
      Returns a string that uniquely identifies this instance. All
      exporters will be sorted by Order before being exported.
      '''
      return 0, self.info.name

   def Header(self):
      return self.info.include

   def __eq__(self, other):
      return type(self) is type(other) and self.Name() == other.Name() \
             and self.interface_file == other.interface_file

   def __ne__(self, other):
      return not self == other
