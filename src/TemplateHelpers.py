# $Id: TemplateHelpers.py,v 1.1 2003-10-01 22:48:52 patrick Exp $

def getCPlusPlusName(decl, translateProblemTypes = True):
   if not translateProblemTypes:
      return decl.FullName()
   else:
      name = []
      for n in decl.getFullNameAbstract():
         if n.startswith("basic_string"):
            if decl.const:
               name = ['const char*']
            else:
               name = ['char*']
            break
         else:
            name.append(n)

      return '::'.join(name)

def getCSharpName(decl, translateProblemTypes = True):
   if not translateProblemTypes:
      return '.'.join(decl.getFullNameAbstract())
   else:
      name = []
      for n in decl.getFullNameAbstract():
         if n.startswith("basic_string"):
            name = ['String']
            break
         else:
            name.append(n)

      return '.'.join(name)

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
