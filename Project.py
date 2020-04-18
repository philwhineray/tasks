#!/usr/bin/env python3

import re

class Project:
   def __init__( self, title ):
      self.shortId = None
      self.apiRef = None
      self.apiObject = None
      self.title = title

   def __str__( self ):
      return self.title

class Matcher():
   def match( self, task ):
      NotImplementedError( "must subclass Project.Matcher" )

class WordMatcher( Matcher ):
   def __init__( self, word ):
      self.word = word

   def match( self, project ):
      if self.word == project.shortId:
         return True
      return re.search( self.word, project.title, flags=re.IGNORECASE )
