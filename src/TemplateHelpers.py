# $Id: TemplateHelpers.py,v 1.8 2003-11-14 17:43:07 patrick Exp $

def getDeclName(decl, visitor):
   decl.accept(visitor)
   return visitor.getRawName()

def getDeclUsage(decl, visitor):
   decl.accept(visitor)
   return visitor.getUsage()

def makeCPlusPlusTypedef(func):
   def getCPlusPlusName(decl):
      return decl.FullName()

   param_types = ', '.join([p[0].FullName() for p in func.parameters])
   typedef = 'typedef %s (*%s_t)(%s)' % \
             (getCPlusPlusName(func.result), getCallbackName(func),
              param_types)
   return typedef

def getCallbackName(methodDecl):
   '''
   Returns the name of the C callback that corresponds with the given method
   declaration.
   '''
   name = methodDecl.name[0] + '_callback'
   if len(methodDecl.parameters) > 0:
      params = [x[0].getCleanName() for x in methodDecl.parameters]
      name = name + '_' + '_'.join(params)
   return name

def getDelegateName(methodDecl):
   '''
   Returns the name of the C# delegate that corresponds with the given method
   declaration.
   '''
   name = methodDecl.name[0] + 'Delegate'
   if len(methodDecl.parameters) > 0:
      params = [x[0].getCleanName() for x in methodDecl.parameters]
      name = name + '_' + '_'.join(params)
   return name

def getBridgeName(classVisitor):
   return classVisitor.getGenericName() + '_Bridge'

def getHolderName(classVisitor):
   return classVisitor.getGenericName() + '_Holder'

def getSelfType(classObj, classVisitor):
   if classObj.info.only_smart_ptr:
      return getHolderName(classVisitor) + '*'
   else:
      return classVisitor.getRawName() + '*'
      