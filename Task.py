#!/usr/bin/env python3

from datetime import datetime
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

class TaskDueMatcher( TaskMatcher ):
   def __init__( self, due ):
      if due[ 0 : 2 ] == "+=" or due[ 0 : 2 ] == "=+":
         self.dueRelative = "onOrAfter"
         dueDate = due[ 2: ]
      elif due[ 0 : 2 ] == "-=" or due[ 0 : 2 ] == "=-":
         self.dueRelative = "onOrBefore"
         dueDate = due[ 2: ]
      elif due[ 0 ] == "+":
         self.dueRelative = "after"
         dueDate = due[ 1: ]
      elif due[ 0 ] == "-":
         self.dueRelative = "before"
         dueDate = due[ 1: ]
      elif due[ 0 ] == "=":
         self.dueRelative = "on"
         dueDate = due[ 1: ]
      else:
         self.dueRelative = "on"
         dueDate = due

      if dueDate == "today" or dueDate == "now":
         now = datetime.now()
         dueDate = now.strftime( "%Y-%m-%d" )
      elif not re.match( "[0-9]{4}-[0-9]{2}-[0-9]{2}$", dueDate ):
         raise RuntimeError( "due format must be due:[+-=]yyyy-mm-dd" )

      self.due = dueDate

   def match( self, task ):
      due = task.apiObject.get( 'due' )
      if not due:
         return False
      due = due[ :10 ]
      if self.dueRelative == "before":
         return due < self.due
      elif self.dueRelative == "onOrBefore":
         return due <= self.due
      elif self.dueRelative == "after":
         return due > self.due
      elif self.dueRelative == "onOrAfter":
         return due >= self.due
      return due == self.due
