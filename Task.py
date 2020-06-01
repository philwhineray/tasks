#!/usr/bin/env python3

from datetime import datetime
import functools
import re
import sys

import Matcher

class Task():
   def __init__( self, project ):
      self.shortId = None
      self._project = project
      self._project.addTask( self )
      self._parentTask = None
      self.childTasks = set()
      self.previousTask = 0
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

   def get_parentTask( self ):
      return self._parentTask

   def set_parentTask( self, parentTask ):
      if self._parentTask:
         self._parentTask.childTasks.remove( self )
      self._parentTask = parentTask
      if self._parentTask:
         self._parentTask.childTasks.add( self )

   parentTask = property( get_parentTask, set_parentTask )

   def save( self ):
      raise NotImplementedError( "must subclass Task.Task" )

   def delete( self ):
      raise NotImplementedError( "must subclass Task.Task" )

   def apiOrderKey( self ):
      raise NotImplementedError( "must subclass Task.Task" )

   def hasAncestor( self, possibleAncestor ):
      parent = self.parentTask
      while parent:
         if parent == possibleAncestor:
            return True
         parent = parent.parentTask
      return False

   def level( self ):
      l = 0
      parent = self.parentTask
      while parent:
         l += 1
         parent = parent.parentTask
      return l

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
      depth = "**"
      parent = self.parentTask
      while parent:
         depth += "*"
         parent = parent.parentTask
      return depth + " (" + self.shortId + ") " + completeMark + " " + str( self )

   def print( self, options=None, outfile=sys.stdout ):
      print( self.lineString(), file=outfile )
      if options and "verbose" in options and self.notes is not None:
         print( self.notes, file=outfile )
         print( "", file=outfile )

   def parse( project, line ):
      match = re.match( r"\*(\*+) \((t[0-9a-f]*)\) +\[([ X-])\] +(\[([0-9-]+)\] +)?(.*)", line )
      if match:
         if not project:
            return True
         task = Task( project )
         task.shortId = match[ 2 ]
         task.complete = match[ 3 ].upper() == 'X'
         task.dueDate = match[ 5 ]
         task.title = match[ 6 ]
         deleted = match[ 3 ] == '-'
         level = len( match[ 1 ] ) - 1
         return task, deleted, level
      return None

   def sortKey( self, alphabetic ):
      def partialKey( task, alphabetic ):
         def earliestDue( task ):
            dueDate = task.dueDate if task.dueDate else "ZZZZ-ZZ-ZZ"
            for t in task.childTasks:
               d = earliestDue( t )
               if d < dueDate:
                  dueDate = d
            return dueDate

         dateKey = earliestDue( task )
         posKey = task.title.upper() if alphabetic else task.apiOrderKey()
         return ( dateKey, posKey )

      key = []
      task = self
      while task:
         key.insert( 0, partialKey( task, alphabetic ) )
         task = task.parentTask
      return key

   def alphabeticalKey( self ):
      return self.sortKey( True )

   def positionKey( self ):
      return self.sortKey( False )

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
