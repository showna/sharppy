# $Id: TemplateHelpers.py,v 1.15 2004-02-26 00:31:46 patrick Exp $

def getDeclName(decl, visitor):
   decl.accept(visitor)
   return visitor.getRawName()

def getDeclUsage(decl, visitor):
   decl.accept(visitor)
   return visitor.getUsage()

def getDelegateName(methodDecl):
   '''
   Returns the name of the C# delegate that corresponds with the given method
   declaration.
   '''
   name = methodDecl.name[0] + 'Delegate'
   if len(methodDecl.parameters) > 0:
      params = [x[0].getID() for x in methodDecl.parameters]
      name = name + '_' + '_'.join(params)
   return name

def getAdapterName(classVisitor):
   return classVisitor.getGenericName() + '_Adapter'

def getHolderName(classVisitor):
   return classVisitor.getGenericName() + '_Holder'
