# This is derived from the Pyste version of CodeExporter.py.
# See http://www.boost.org/ for more information.

import Exporter

#==============================================================================
# CodeExporter
#==============================================================================
class CodeExporter(Exporter.Exporter):

    def __init__(self, info):
        Exporter.Exporter.__init__(self, info)


    def Name(self):
        return self.info.code


    def Export(self, codeunit, exported_names):
        codeunit.Write(self.info.section, self.info.code)        
