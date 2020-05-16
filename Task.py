#!/usr/bin/env python3

from datetime import datetime
import re
import sys

import Matcher

class Task():
   def __init__( self, project ):
      self.shortId = None
      self._project = project
      self._project.addTask( self )
      self.title = None
      self.notes = None
      self.complete = False
      self.dueDate = None
      self.dueTime = None

   def get_project( self ):
      return self._project

   def set_project( self, project ):
      self._project.removeTask( self )
      self._project = project
      self._project.addTask( self )

   project = property( get_project, set_project )

   def save( self ):
      raise NotImplementedError( "must subclass Project.Project" )

   def delete( self ):
      raise NotImplementedError( "must subclass Project.Project" )

   def __str__( self ):
      if self.dueDate:
         due = "[" + self.dueDate
         if self.dueTime:
            due += " " + self.dueTime
         due += "] "
         return due + self.title
      return self.title

   def lineString( self ):
      if self.complete:
         completeMark = "[X]"
      else:
         completeMark = "[ ]"
      return self.shortId + " " + completeMark + " " + str( self )

   def print( self, options=None, outfile=sys.stdout ):
      print( self.lineString(), file=outfile )
      if options and "verbose" in options and self.notes is not None:
         print( self.notes, file=outfile )
         print( "", file=outfile )

   def parse( project, line ):
      match = re.match( r"(t[0-9a-f]+) +\[([ X-])\] +(\[([0-9-]+)\] +)?(.*)", line )
      if match:
         task = Task( project )
         task.shortId = match[ 1 ]
         task.complete = match[ 2 ] == 'X'
         task.dueDate = match[ 4 ]
         task.title = match[ 5 ]
         deleted = match[ 2 ] == '-'
         return task, deleted
      return None

def sort( tasks ):
   # Ensure items with due dates are at the top and in order.
   return sorted( tasks, key=lambda t: ( t.apiObject.get( 'due', "ZZZZ" ), t.title.upper() ) )

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
