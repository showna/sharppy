#!/usr/bin/env python

# This is derived from the Pyste version of pyste.py.
# See http://www.boost.org/ for more information.

# $Id: sharppy.py,v 1.22 2004-02-24 18:15:44 patrick Exp $

"""
Sharppy version %s

Usage:
    sharppy [options] interface-files

where options are:
    --module=<name>         The name of the module that will be generated;
                            defaults to the first interface filename, without
                            the extension.
    -I <path>               Add an include path
    -D <symbol>             Define symbol
    --out-cxx=<name>        Specify C++ output directory (default: <module>_cpp)
    --out-csharp=<name>     Specify C# output directory (default: <module>_cs)
    --sharppy-ns=<name>     Set the namespace where new types will be declared;
                            default is the empty namespace
    --debug                 Writes the xml for each file parsed in the current
                            directory
    --cache-dir=<dir>       Directory for cache files (speeds up future runs)
    --only-create-cache     Recreates all caches (doesn't generate code).
    -h, --help              Print this help and exit
    -v, --version           Print version information
"""

import sys
import os
import getopt
import exporters
import infos
import exporterutils
import settings
import gc
import sys
import policies
import CppParser
import time
import declarations

__version__ = '0.0.1'


def RecursiveIncludes(include):
   'Return a list containg the include dir and all its subdirectories'
   dirs = [include]
   def visit(arg, dir, names):
      # ignore CVS dirs
      if os.path.split(dir)[1] != 'CVS':
         dirs.append(dir)
   os.path.walk(include, visit, None)
   return dirs

def GetDefaultIncludeDirs():
   if 'INCLUDE' in os.environ:
      include = os.environ['INCLUDE']
      return include.split(os.pathsep)
   else:
      return []


def ProcessIncludeDirs(includeDirs):
   if sys.platform == 'win32':
      index = 0
      for dir in includeDirs:
         includeDirs[index] = dir.replace('\\', '/')
         index += 1

def ParseArguments():
   def Usage():
      print __doc__ % __version__
      sys.exit(1)

   try:
      options, files = getopt.getopt(sys.argv[1:], 'R:I:D:vh',
                                     ['out-cxx=', 'out-csharp=',
                                      'sharppy-ns=', 'debug', 'cache-dir=',
                                      'only-create-cache', 'version', 'help'])
   except getopt.GetoptError, e:
      print
      print 'ERROR:', e
      Usage()

   include_dirs = GetDefaultIncludeDirs()
   defines = []
   out_cxx = None
   out_csharp = None
   cache_dir = None
   create_cache = False

   for opt, value in options:
      if opt == '-I':
         include_dirs.append(value)
      elif opt == '-D':
         defines.append(value)
      elif opt == '-R':
         include_dirs.extend(RecursiveIncludes(value))
      elif opt == '--out-cxx':
         out_cxx = value
      elif opt == '--out-csharp':
         out_csharp = value
      elif opt == '--sharppy-ns':
         settings.namespaces.sharppy = value + '::'
      elif opt == '--debug':
         settings.DEBUG = True
      elif opt == '--cache-dir':
         cache_dir = value
      elif opt == '--only-create-cache':
         create_cache = True
      elif opt in ['-h', '--help']:
         Usage()
      elif opt in ['-v', '--version']:
         print 'Sharppy version %s' % __version__
         sys.exit(2)
      else:
         print 'Unknown option:', opt
         Usage()

   if not files:
      Usage()

   for file in files:
      d = os.path.dirname(os.path.abspath(file))
      if d not in sys.path:
         sys.path.append(d)

   if create_cache and not cache_dir:
      print 'Error: Use --cache-dir to indicate where to create the cache files!'
      Usage()
      sys.exit(3)

   ProcessIncludeDirs(include_dirs)
   return include_dirs, defines, out_cxx, out_csharp, files, cache_dir, create_cache

def CreateContext():
   'create the context where a interface file will be executed'
   context = {}
   context['Import'] = ExecuteInterface
   # infos
   context['FreeTypesHolder'] = infos.FreeTypesHolderInfo
   context['ValueType'] = infos.ValueTypeInfo
   context['ReferenceType'] = infos.ReferenceTypeInfo
   context['ReferenceTemplate'] = infos.ReferenceTypeTemplateInfo
   context['ValueTemplate'] = infos.ValueTypeTemplateInfo
#   context['AllFromHeader'] = infos.HeaderInfo
   context['Var'] = infos.VarInfo
   # functions
   context['rename'] = infos.rename
   context['set_policy'] = infos.set_policy
   context['exclude'] = infos.exclude
   context['property'] = infos.property
   context['readonly'] = infos.readonly
   context['set_wrapper'] = infos.set_wrapper
   context['use_smart_ptr'] = infos.use_smart_ptr
   context['use_shared_ptr'] = infos.use_shared_ptr
   context['use_auto_ptr'] = infos.use_auto_ptr
   context['no_smart_ptr'] = infos.no_smart_ptr
   context['holder'] = infos.holder
   context['add_method'] = infos.add_method
   context['sealed'] = infos.sealed
   context['return_array'] = infos.return_array
   # policies
   context['return_internal_reference'] = policies.return_internal_reference
   context['with_custodian_and_ward'] = policies.with_custodian_and_ward
   context['return_value_policy'] = policies.return_value_policy
   context['reference_existing_object'] = policies.reference_existing_object
   context['copy_const_reference'] = policies.copy_const_reference
   context['copy_non_const_reference'] = policies.copy_non_const_reference
   context['return_opaque_pointer'] = policies.return_opaque_pointer
   context['manage_new_object'] = policies.manage_new_object
   # utils
   context['Wrapper'] = exporterutils.FunctionWrapper
   context['declaration_code'] = lambda code: infos.CodeInfo(code, 'declaration-outside')
   context['module_code'] = lambda code: infos.CodeInfo(code, 'module')
   return context

def Begin():
   # parse arguments
   include_dirs, defines, out_cxx, out_csharp, interfaces, cache_dir, create_cache = ParseArguments()
   # run sharppy scripts
   for interface in interfaces:
      ExecuteInterface(interface)
   # create the parser
   parser = CppParser.CppParser(include_dirs, defines, cache_dir,
                                declarations.version)
   try:
      if not create_cache:
         return GenerateCode(parser, out_cxx, out_csharp, interfaces)
      else:
         return CreateCaches(parser)
   finally:
      parser.Close()

def CreateCaches(parser):
   # There is one cache file per interface so we organize the headers
   # by interfaces.  For each interface collect the tails from the
   # exporters sharing the same header.
   tails = JoinTails(exporters.exporters)

   # now for each interface file take each header, and using the tail
   # get the declarations and cache them.
   for interface, header in tails:
      tail = tails[(interface, header)]
      declarations = parser.ParseWithGCCXML(header, tail)
      cachefile = parser.CreateCache(header, interface, tail, declarations)
      print 'Cached', cachefile

   return 0


_imported_count = {}  # interface => count

def ExecuteInterface(interface):
   old_interface = exporters.current_interface
   if not os.path.exists(interface):
      if old_interface and os.path.exists(old_interface):
         d = os.path.dirname(old_interface)
         interface = os.path.join(d, interface)
   if not os.path.exists(interface):
      raise IOError, "Cannot find interface file %s."%interface

   _imported_count[interface] = _imported_count.get(interface, 0) + 1
   exporters.current_interface = interface
   context = CreateContext()
   execfile(interface, context)
   exporters.current_interface = old_interface


def JoinTails(exports):
   '''Returns a dict of {(interface, header): tail}, where tail is the
   joining of all tails of all exports for the header.
   '''
   tails = {}
   for export in exports:
      interface = export.interface_file
      header = export.Header()
      tail = export.Tail() or ''
      if (interface, header) in tails:
         all_tails = tails[(interface,header)]
         all_tails += '\n' + tail
         tails[(interface, header)] = all_tails
      else:
         tails[(interface, header)] = tail

   return tails


def OrderInterfaces(interfaces):
   interfaces_order = [(_imported_count[x], x) for x in interfaces]
   interfaces_order.sort()
   interfaces_order.reverse()
   return [x for _, x in interfaces_order]


def GenerateCode(parser, out_cxx, out_csharp, interfaces):
   # stop referencing the exporters here
   exports = exporters.exporters
   exporters.exporters = None
   exported_names = dict([(x.Name(), None) for x in exports])

   # order the exports
   order = {}
   for export in exports:
      if export.interface_file in order:
         order[export.interface_file].append(export)
      else:
         order[export.interface_file] = [export]
   exports = []
   interfaces_order = OrderInterfaces(interfaces)
   for interface in interfaces_order:
      exports.extend(order[interface])
   del order
   del interfaces_order

   modules = []

   # now generate the code in the correct order
   #print exported_names
   tails = JoinTails(exports)
   export_count = len(exports)
   for i in xrange(len(exports)):
      export = exports[i]
      progress = float(i) / float(export_count)
      print "Exporting %s (%3.2f%%)" % (export.Name(), progress * 100.0)
      interface = export.interface_file
      header = export.Header()
      if header:
         tail = tails[(interface, header)]
         # declarations contains everything read in from parsing header.
         print "\tParsing %s..." % header,
         sys.__stdout__.flush()
         declarations, parsed_header = parser.Parse(header, interface, tail)
         print "Done."
      else:
         declarations = []
         parsed_header = None
      ExpandTypedefs(declarations, exported_names)
      if export.info.module not in modules:
         modules.append(export.info.module)
      export.SetDeclarations(declarations)
      export.SetParsedHeader(parsed_header)
      export.GenerateCode(exported_names)
      # force collect of cyclic references
      exports[i] = None
      del declarations
      del export
      gc.collect()

   print 'Modules (%s) generated' % ', '.join(modules)
   return 0

def ExpandTypedefs(decls, exported_names):
   '''Check if the names in exported_names are a typedef, and add the real
   class name in the dict.
   '''
   for name in exported_names.keys():
      for decl in decls:
         if isinstance(decl, declarations.Typedef):
            exported_names[decl.type.getFullCPlusPlusName()] = None

def UsePsyco():
   'Tries to use psyco if possible'
   try:
      import psyco
      psyco.profile()
   except: pass


def main():
   start = time.clock()
   UsePsyco()
   status = Begin()
   print '%0.2f seconds' % (time.clock()-start)
   sys.exit(status)


if __name__ == '__main__':
   main()
