#!/usr/bin/env python3

import re
import Matcher

class Project:
   def __init__( self, title ):
      self.shortId = None
      self.apiRef = None
      self.apiObject = None
      self.title = title

   def __str__( self ):
      return self.title

class ProjectMatcher( Matcher.Matcher ):
   def isProject( projectOrTask ):
      return isinstance( projectOrTask, Project )

class WordMatcher( ProjectMatcher ):
   def __init__( self, word ):
      self.word = word

   def match( self, projectOrTask ):
      if ProjectMatcher.isProject( projectOrTask ):
         project = projectOrTask
      else:
         project = projectOrTask.project
      if self.word == project.shortId:
         return True
      return re.search( self.word, project.title, flags=re.IGNORECASE )
