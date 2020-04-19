#!/usr/bin/env python3

import re

class Matcher():
   def __init__( self ):
      self.debug = False

   def match( self, projectOrTask ):
      NotImplementedError( "must subclass Matcher.Matcher" )

class Group( Matcher ):
   def __init__( self ):
      super().__init__()
      self.matchers = []
      self.parent = None

   def add( self, matcher ):
      self.matchers.append( matcher )
      matcher.parent = self
      matcher.debug = self.debug

class And( Group ):
   def match( self, projectOrTask ):
      if self.debug:
         print( "And", "match?" )
      for matcher in self.matchers:
         if not matcher.match( projectOrTask ):
            if self.debug:
               print( "And", "no match" )
            return False
      if self.debug:
         print( "And", "match" )
      return True

class Or( Group ):
   def match( self, projectOrTask ):
      if self.debug:
         print( "Or", "match?" )
      for matcher in self.matchers:
         if matcher.match( projectOrTask ):
            if self.debug:
               print( "Or", "match" )
            return True
      if self.debug:
         print( "Or", "no match" )
      return False
