#!/usr/bin/env python3

import re
import sys

class Matcher():
   def __init__( self ):
      self.debug = False

   def match( self, projectOrTask ):
      raise NotImplementedError( "must subclass Matcher.Matcher" )

   def hasInstanceOf( self, classType ):
      return isinstance( self, classType )

class Group( Matcher ):
   def __init__( self ):
      super().__init__()
      self.matchers = []
      self.parent = None

   def add( self, matcher ):
      self.matchers.append( matcher )
      matcher.parent = self
      matcher.debug = self.debug

   def hasInstanceOf( self, classType ):
      for matcher in self.matchers:
         if matcher.hasInstanceOf( classType ):
            return True

class And( Group ):
   def match( self, projectOrTask ):
      if self.debug:
         print( "And", "match?", file=sys.stderr )
      for matcher in self.matchers:
         if not matcher.match( projectOrTask ):
            if self.debug:
               print( "And", "no match", file=sys.stderr )
            return False
      if self.debug:
         print( "And", "match", file=sys.stderr )
      return True

class Or( Group ):
   def match( self, projectOrTask ):
      if self.debug:
         print( "Or", "match?", file=sys.stderr )
      for matcher in self.matchers:
         if matcher.match( projectOrTask ):
            if self.debug:
               print( "Or", "match", file=sys.stderr )
            return True
      if self.debug:
         print( "Or", "no match", file=sys.stderr )
      return False

class Not( Group ):
   def match( self, projectOrTask ):
      if self.debug:
         print( "Not", "match?", file=sys.stderr )
      for matcher in self.matchers:
         if matcher.match( projectOrTask ):
            if self.debug:
               print( "Not", "no match", file=sys.stderr )
            return False
      if self.debug:
         print( "Not", "match", file=sys.stderr )
      return True
