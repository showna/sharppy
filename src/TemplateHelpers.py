# $Id: TemplateHelpers.py,v 1.2 2003-10-09 19:06:10 patrick Exp $

def getCPlusPlusName(decl):
   return decl.FullName()
#   full_name = decl.getFullNameAbstract()
#   if 'basic_string' in full_name:
#      if decl.const:
#         const = 'const '
#      return const + 'char*' + decl.suffix
#   else:
#      return decl.FullName()

def getCSharpName(decl):
   return '.'.join(decl.getFullNameAbstract())
#   if not translateProblemTypes:
#      return '.'.join(decl.getFullNameAbstract())
#   else:
#      name = []
#      for n in decl.getFullNameAbstract():
#         if n.startswith("basic_string"):
#            name = ['String']
#            break
#         else:
#            name.append(n)
#
#      return '.'.join(name)

def getCallbackTypedefName(funcHolder, scoped = False):
   if scoped:
      return '::'.join(funcHolder.scoped_type)
   else:
      return funcHolder.type

def makeCPlusPlusTypedef(funcHolder):
   func = funcHolder.func
   param_types = ', '.join([p[0].FullName() for p in func.parameters])
   typedef = 'typedef %s (%s*)(%s)' % \
             (getCPlusPlusName(func.result), getCallbackTypedefName(funcHolder),
              param_types)
   return typedef
