# $Id: TemplateHelpers.py,v 1.11 2003-12-22 23:12:52 patrick Exp $

def getDeclName(decl, visitor):
   decl.accept(visitor)
   return visitor.getRawName()

def getDeclUsage(decl, visitor):
   decl.accept(visitor)
   return visitor.getUsage()

def makeCPlusPlusTypedef(func):
   def getResultType(resultDecl):
      if resultDecl.must_marshal:
         marshal_ptr = '*'
      else:
         marshal_ptr = ''
      return resultDecl.FullName() + marshal_ptr

   param_types = ', '.join([p[0].FullName() for p in func.parameters])
   typedef = 'typedef %s (*%s_t)(%s)' % \
             (getResultType(func.result), getCallbackName(func),
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

def getAdapterName(classVisitor):
   return classVisitor.getGenericName() + '_Adapter'

def getHolderName(classVisitor):
   return classVisitor.getGenericName() + '_Holder'
