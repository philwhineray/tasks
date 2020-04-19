#!/usr/bin/env python3

import re

class Matcher():
   def match( self, projectOrTask ):
      NotImplementedError( "must subclass Matcher.Matcher" )

class Group( Matcher ):
   def __init__( self ):
      self.matchers = []

   def add( self, matcher ):
      self.matchers.append( matcher )

class And( Group ):
   def match( self, projectOrTask ):
      for matcher in self.matchers:
         if not matcher.match( projectOrTask ):
            return False
      return True

class Or( Group ):
   def match( self, projectOrTask ):
      for matcher in self.matchers:
         if matcher.match( projectOrTask ):
            return True
      return False
