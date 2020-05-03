#!/usr/bin/env python3

import re
import sys

import Matcher

class Project:
   def __init__( self, title ):
      self.shortId = None
      self.title = title
      self.tasks = set()

   def save( self ):
      NotImplementedError( "must subclass Project.Project" )

   def delete( self ):
      NotImplementedError( "must subclass Project.Project" )

   def print( self, options=None, outfile=sys.stdout ):
      print( self.title, file=outfile )

   def __str__( self ):
      return self.title

def sort( projects ):
   return sorted( projects, key=lambda p: p.title if p.title != "Inbox" else "" )

class ProjectMatcher( Matcher.Matcher ):
   def isProject( projectOrTask ):
      return isinstance( projectOrTask, Project )

class WordMatcher( ProjectMatcher ):
   def __init__( self, word ):
      super().__init__()
      self.word = word

   def match( self, projectOrTask ):
      if self.debug:
         print( "Project.Word", "match?", self.word, file=sys.stderr )
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
            print( "Project.Word", "match", file=sys.stderr )
         else:
            print( "Project.Word", "no match", file=sys.stderr )
      return result
