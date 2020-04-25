#!/usr/bin/env python3

import re
import Matcher

class Project:
   def __init__( self, title ):
      self.shortId = None
      self.title = title

   def __str__( self ):
      return self.title

   def save( self ):
      NotImplementedError( "must subclass Project.Project" )

   def delete( self ):
      NotImplementedError( "must subclass Project.Project" )

class ProjectMatcher( Matcher.Matcher ):
   def isProject( projectOrTask ):
      return isinstance( projectOrTask, Project )

class WordMatcher( ProjectMatcher ):
   def __init__( self, word ):
      super().__init__()
      self.word = word

   def match( self, projectOrTask ):
      if self.debug:
         print( "Project.Word", "match?", self.word )
      if ProjectMatcher.isProject( projectOrTask ):
         project = projectOrTask
      else:
         project = projectOrTask.project

      if self.word == project.shortId:
         result = True
      else:
         result = re.search( self.word, project.title, flags=re.IGNORECASE )
      if self.debug:
         if result:
            print( "Project.Word", "match" )
         else:
            print( "Project.Word", "no match" )
      return result
