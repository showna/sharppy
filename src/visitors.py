# $Id: visitors.py,v 1.8 2003-11-10 20:57:05 patrick Exp $

from declarations import Function

class DeclarationVisitor:
   def __init__(self):
      self.name         = None
      self.generic_name = None
      self.usage        = None
      self.no_ns_name   = None

   def visit(self, decl):
      assert("Not implemented")

   def getRawName(self, namespace = True):
      '''
      Returns the raw, unprocessed name of a declaration.
      '''
      if namespace:
         return self.name
      else:
         return self.no_ns_name

   def getGenericName(self):
      '''
      Returns a "generic" name following the rules for identifier names in
      most, if not all, programming languages.
      '''
      return self.generic_name

   def getUsage(self):
      '''
      Returns the safe usage of a declaration.  The definition of "safe" is
      that various internal processing has been performed to make the
      declaration suitable for usage in various situations.
      '''
      return self.usage

   def _makeGenericName(self, decl):
      return '_'.join(decl.getFullNameAbstract())

   def _makeGenericFuncName(self, decl):
      base_name = self._makeGenericName(decl)
      param_types = [x[0].getCleanName() for x in decl.parameters]
      return base_name + '__' +'_'.join(param_types)

class CPlusPlusVisitor(DeclarationVisitor):
   '''
   Basic, general-purpose C++ visitor.
   '''
   def __init__(self):
      DeclarationVisitor.__init__(self)

   def visit(self, decl):
      full_name = decl.getFullNameAbstract()
      self.name = decl.FullName()

      if isinstance(decl, Function):
         self.generic_name = self._makeGenericFuncName(decl)
      else:
         self.generic_name = self._makeGenericName(decl)

      self.no_ns_name = '::'.join(decl.name)
      self.usage = self.name

      # Deal with types that need special handling.
      for s in full_name:
         if s.find('basic_string') != -1:
            const = ''
            if decl.const:
               const = 'const '

            # XXX: How do we deal with by-reference parameters?
            self.usage = const + 'char*' # + decl.suffix
            decl.must_marshal = False
            break

class CPlusPlusParamVisitor(CPlusPlusVisitor):
   '''
   C++ visitor for function/method parameters.  This will handle the details
   associated with parameter types when marshaling is in effect.
   '''
   def __init__(self):
      CPlusPlusVisitor.__init__(self)

   def visit(self, decl):
      CPlusPlusVisitor.visit(self, decl)

class CPlusPlusReturnVisitor(CPlusPlusVisitor):
   '''
   C++ visitor for return type declarations.
   '''
   def __init__(self):
      CPlusPlusVisitor.__init__(self)

   def visit(self, decl):
      CPlusPlusVisitor.visit(self, decl)
      if decl.must_marshal:
         self.usage = self.usage + '*'

class CSharpVisitor(DeclarationVisitor):
   '''
   Basic, general-purpose C# visitor.
   '''
   def __init__(self):
      DeclarationVisitor.__init__(self)

   def visit(self, decl):
      full_name = decl.getFullNameAbstract()
      self.name = '.'.join(full_name)

      if isinstance(decl, Function):
         self.generic_name = self._makeGenericFuncName(decl)
      else:
         self.generic_name = self._makeGenericName(decl)

      self.no_ns_name = '.'.join(decl.name)
      self.usage = self.name

      # Deal with types that need special handling.
      # XXX: Figure out if there is a simpler way of dealing with unsigned
      # integers.  It depends largely on the order that the type information
      # is returned ("int unsigned" versus "unsigned int").
      for s in full_name:
         if s.find('basic_string') != -1:
            self.usage = 'String'
            decl.must_marshal = False
            break
         # Using long long probably indicates a desire for a 64-bit integer.
         elif s.find('long long') != -1:
            if s.find('unsigned') != -1:
               self.usage = 'ulong'
            else:
               self.usage = 'long'
            break
         # Assume that a long (not a long long) is supposed to be a 32-bit
         # integer.
         elif s.find('long') != -1 or s.find('int') != -1:
            if s.find('unsigned') != -1:
               self.usage = 'uint'
            else:
               self.usage = 'int'
            break
         # Translate char, which is 1 byte in C/C++, into byte.
         elif s.find('char') != -1:
            if s.find('unsigned') != -1:
               self.usage = 'byte'
            else:
               self.usage = 'sbyte'
            break

class CSharpParamVisitor(CSharpVisitor):
   '''
   C# visitor for function/method parameters.  This will handle the details
   associated with parameter types when marshaling is in effect.
   '''
   def __init__(self):
      CSharpVisitor.__init__(self)

   def visit(self, decl):
      CSharpVisitor.visit(self, decl)

class CSharpReturnVisitor(CSharpVisitor):
   '''
   C# visitor for return type declarations.  This will handle the details
   associated with return types when marshaling is in effect.
   '''
   def __init__(self):
      CSharpVisitor.__init__(self)

   def visit(self, decl):
      CSharpVisitor.visit(self, decl)
