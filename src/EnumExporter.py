# This is derived from the Pyste version of EnumExporter.py.
# See http://www.boost.org/ for more information.

# $Id: EnumExporter.py,v 1.3 2003-11-03 23:36:09 patrick Exp $

from Exporter import Exporter

#==============================================================================
# EnumExporter
#==============================================================================
class EnumExporter(Exporter):
   'Exports enumerators'

   def __init__(self, info):
      Exporter.__init__(self, info)

   def SetDeclarations(self, declarations):
      Exporter.SetDeclarations(self, declarations)
      if self.declarations:
         self.enum = self.GetDeclaration(self.info.name)
      else:
         self.enum = None

   def Export(self, exported_names):
      if not self.info.exclude:
         exported_names[self.Name()] = 1

   def Name(self):
      return self.info.name
