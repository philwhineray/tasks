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
      self.notes = None
      self.complete = False
      self.dueDate = None
      self.dueTime = None

   def save( self ):
      NotImplementedError( "must subclass Project.Project" )

   def delete( self ):
      NotImplementedError( "must subclass Project.Project" )

   def __str__( self ):
      if self.dueDate:
         due = "[" + self.dueDate
         if self.dueTime:
            due += " " + self.dueTime
         due += "] "
         return due + self.title
      return self.title

   def lineString( self ):
      completeMark = "[X]" if self.complete else "[ ]"
      return self.shortId + " " + completeMark + " " + str( self )

   def print( self, options=None, outfile=sys.stdout ):
      print( self.lineString(), file=outfile )
      if options and "verbose" in options and self.notes is not None:
         print( "  ", self.notes, file=outfile )

class TaskMatcher( Matcher.Matcher ):
   def isTask( projectOrTask ):
      return isinstance( projectOrTask, Task )

class WordMatcher( TaskMatcher ):
   def __init__( self, word ):
      super().__init__()
      self.word = word

   def match( self, projectOrTask ):
      if self.debug:
         print( "Task.Word", "match?", self.word, file=sys.stderr )
      if TaskMatcher.isTask( projectOrTask ):
         task = projectOrTask
      else:
         if self.debug:
            print( "Task.Word", "no match", file=sys.stderr )
         return False
      if self.word == task.shortId:
         result = True
      else:
         result = re.search( self.word, task.title, flags=re.IGNORECASE )
      if self.debug:
         if result:
            print( "Task.Word", "match", file=sys.stderr )
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
         print( "Due", "match?", self.dueRelative, self.due, file=sys.stderr )
      if TaskMatcher.isTask( projectOrTask ):
         task = projectOrTask
      else:
         if self.debug:
            print( "Due", "no match", file=sys.stderr )
         return False
      if not task.dueDate:
         if self.debug:
            print( "Due", "no match", file=sys.stderr )
         return False
      if self.dueRelative == "before":
         result = task.dueDate < self.due
      elif self.dueRelative == "onOrBefore":
         result = task.dueDate <= self.due
      elif self.dueRelative == "after":
         result = task.dueDate > self.due
      elif self.dueRelative == "onOrAfter":
         result = task.dueDate >= self.due
      else:
         result = task.dueDate == self.due
      if self.debug:
         if result:
            print( "Due", "match", file=sys.stderr )
         else:
            print( "Due", "no match" )
      return result
