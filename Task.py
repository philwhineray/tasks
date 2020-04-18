#!/usr/bin/env python3

import re

class Task:
   def __init__( self, project, title ):
      self.shortId = None
      self.apiRef = None
      self.apiObject = None
      self.project = project
      self.title = title
      self.complete = False

   def __str__( self ):
      due = ""
      if 'due' in self.apiObject:
         due = "["
         if self.apiObject[ 'due' ][ 10: ] == "T00:00:00.000Z":
            due += self.apiObject[ 'due' ][ :10 ]
         else:
            due += self.apiObject[ 'due' ][ :16 ]
         due += "] "
      return due + self.title

   def lineString( self ):
      completeMark = "[X]" if self.complete else "[ ]"
      return self.shortId + " " + completeMark + " " + str( self )

class TaskMatcher():
   def match( self, task ):
      NotImplementedError( "must subclass TaskMatcher" )

class TaskWordMatcher( TaskMatcher ):
   def __init__( self, word ):
      self.word = word

   def match( self, task ):
      if self.word == task.shortId:
         return True
      return re.search( self.word, task.title, flags=re.IGNORECASE )
