# This is derived from the Pyste version of FunctionExporter.py.
# See http://www.boost.org/ for more information.

# $Id: FreeTypesExporter.py,v 1.2 2004-02-18 23:40:09 patrick Exp $

import Exporter
import os
import sys

import Cheetah.Template as ct


#==============================================================================
# FreeTypesExporter
#==============================================================================
class FreeTypesExporter(Exporter.Exporter):
   'Generates C# P/Invoke bridging code to one or more export free functions.'

   c_wrapper_template_file = os.path.dirname(__file__) + '/free_types_cxx.tmpl'
   csharp_template_file    = os.path.dirname(__file__) + '/free_types_cs.tmpl'
 
   def __init__(self, info, tail = None):
      Exporter.Exporter.__init__(self, info, tail)
      self.c_wrapper_template = ct.Template(file = self.c_wrapper_template_file)
      self.csharp_template = ct.Template(file = self.csharp_template_file)
      self.funcs     = []
      self.enums     = []
      self.constants = []

   def __printDot(self):
      print "\b.",
      sys.__stdout__.flush()

   def Export(self, exportedNames):
      # Set up the Cheetah template file names.
      base_fname = self.Name()
      self.c_wrapper_output_file = base_fname + '.cpp'
      self.csharp_output_file = base_fname + '.cs'

      for f in self.info.funcs:
         decls = self.GetDeclarations(f)
         if decls:
            self.funcs += decls
            exportedNames[f] = 1

      for e in self.info.enums:
         decl = self.GetDeclaration(e)
         if decl:
            self.enums.append(decl)
            exportedNames[e] = 1

      for c in self.info.constants:
         decl = self.GetDeclaration(c)
         if decl:
            self.constants.append(decl)
            exportedNames[c] = 1

   def Write(self):
      # Set up the mapping information for the templates.
      self.c_wrapper_template.wrapper  = self
      self.c_wrapper_template.module   = self.module
      self.csharp_template.wrapper     = self
      self.csharp_template.module      = self.module
      self.csharp_template.bridge_name = self.module_bridge
      self.csharp_template.class_name  = self.info.holder_class

      c_wrapper_out = os.path.join(self.cxx_dir, self.c_wrapper_output_file)
      csharp_out = os.path.join(self.csharp_dir, self.csharp_output_file)

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

   def Name(self):
      return self.info.holder_class
