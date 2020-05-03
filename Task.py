#!/usr/bin/env python3

from datetime import datetime
import re
import sys

import Matcher

class Task():
   def __init__( self, project, title ):
      self.shortId = None
      self.project = project
      self.title = title
      self.complete = False

   def save( self ):
      NotImplementedError( "must subclass Project.Project" )

   def delete( self ):
      NotImplementedError( "must subclass Project.Project" )

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

   def print( self, options=None, outfile=sys.stdout ):
      print( self.lineString(), file=outfile )
      if options and "verbose" in options and "notes" in self.apiObject:
         print( "  ", self.apiObject[ "notes" ], file=outfile )

class TaskMatcher( Matcher.Matcher ):
   def isTask( projectOrTask ):
      return isinstance( projectOrTask, Task )

class WordMatcher( TaskMatcher ):
   def __init__( self, word ):
      super().__init__()
      self.word = word

   def match( self, projectOrTask ):
      if self.debug:
         print( "Task.Word", "match?", self.word )
      if TaskMatcher.isTask( projectOrTask ):
         task = projectOrTask
      else:
         if self.debug:
            print( "Task.Word", "no match" )
         return False
      if self.word == task.shortId:
         result = True
      else:
         result = re.search( self.word, task.title, flags=re.IGNORECASE )
      if self.debug:
         if result:
            print( "Task.Word", "match" )
         else:
            print( "Task.Word", "no match" )
      return result

class DueMatcher( TaskMatcher ):
   def __init__( self, due ):
      super().__init__()
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

   def match( self, projectOrTask ):
      if self.debug:
         print( "Due", "match?", self.dueRelative, self.due )
      if TaskMatcher.isTask( projectOrTask ):
         task = projectOrTask
      else:
         if self.debug:
            print( "Due", "no match" )
         return False
      due = task.apiObject.get( 'due' )
      if not due:
         if self.debug:
            print( "Due", "no match" )
         return False
      due = due[ :10 ]
      if self.dueRelative == "before":
         result = due < self.due
      elif self.dueRelative == "onOrBefore":
         result = due <= self.due
      elif self.dueRelative == "after":
         result = due > self.due
      elif self.dueRelative == "onOrAfter":
         result = due >= self.due
      else:
         result = due == self.due
      if self.debug:
         if result:
            print( "Due", "match" )
         else:
            print( "Due", "no match" )
      return result
