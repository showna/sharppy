# $Id: TemplateHelpers.py,v 1.5 2003-11-10 20:38:24 patrick Exp $

def getDeclName(decl, visitor):
   decl.accept(visitor)
   return visitor.getRawName()

def getDeclUsage(decl, visitor):
   decl.accept(visitor)
   return visitor.getUsage()

def getCallbackTypedefName(funcHolder, scoped = False):
   if scoped:
      return '::'.join(funcHolder.scoped_type)
   else:
      return funcHolder.type

def makeCPlusPlusTypedef(funcHolder):
   def getCPlusPlusName(decl):
      return decl.FullName()

   func = funcHolder.func
   param_types = ', '.join([p[0].FullName() for p in func.parameters])
   typedef = 'typedef %s (*%s)(%s)' % \
             (getCPlusPlusName(func.result), getCallbackTypedefName(funcHolder),
              param_types)
   return typedef

def getDelegateName(methodDecl):
   name = methodDecl.name[0] + 'Delegate'
   if len(methodDecl.parameters) > 0:
      params = [x[0].getCleanName() for x in methodDecl.parameters]
      name = name + '_' + '_'.join(params)
   return name
