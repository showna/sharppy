# $Id: TemplateHelpers.py,v 1.4 2003-11-04 23:37:39 patrick Exp $

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
