#!/usr/bin/env python3

import re
import sys

import Matcher
import Task

class Project:
   def __init__( self, title ):
      self.shortId = None
      self.title = title
      self._tasks = set()

   def save( self ):
      raise NotImplementedError( "must subclass Project.Project" )

   def delete( self ):
      raise NotImplementedError( "must subclass Project.Project" )

   def newTask( self ):
      raise NotImplementedError( "must subclass Project.Project" )

   def addTask( self, task ):
      self._tasks.add( task )

   def removeTask( self, task ):
      self._tasks.add( task )

   def get_tasks( self ):
      return self._tasks

   tasks = property( get_tasks )

   def __str__( self ):
      return "* (" + self.shortId + ") " + self.title

   def print( self, options=None, outfile=sys.stdout ):
      print( self, file=outfile )

   def matchingTasks( self, options, criteria ):
      match = set()
      for task in self.tasks:
         if "debugMatching" in options:
            print( "", file=sys.stderr )
            print( "Matching...", task, file=sys.stderr )
         if "all" not in options and task.complete:
            if "debugMatching" in options:
               print( "Rejected: Completed and not 'all'", file=sys.stderr )
            continue
         if criteria.match( task ):
            if "debugMatching" in options:
               print( "Accepted", file=sys.stderr )
            match.add( task )
         else:
            if "debugMatching" in options:
               print( "Rejected", file=sys.stderr )
      return match

   def sort( projects ):
      return sorted( projects, key=lambda p: p.title if p.title != "Inbox" else "" )

def write( projects, options, criteria, outfile=sys.stdout ):
   printedProject = set()

   # Force reading of all tasks, so we get consistent short Ids.
   for project in Project.sort( projects ):
      _ = project.tasks

   for project in Project.sort( projects ):

      def printProjectIfNeeded():
         if project in printedProject:
            return
         if printedProject:
            print( "", file=outfile )
         project.print( options=options, outfile=outfile )
         printedProject.add( project )

      if "all" in options or "includeEmptyProjects" in options:
         printProjectIfNeeded()

      for task in Task.sort( project.tasks ):
         if task.complete and "all" not in options:
            continue
         if criteria.match( task ):
            printProjectIfNeeded()
            task.print( options=options, outfile=outfile )

def read( projects, options, infile=None ):
   projectByName = {}
   taskById = {}
   for project in projects:
      projectByName[ project.title ] = project
      for task in project.tasks:
         taskById[ task.shortId ] = task

   toSave = set()
   project = None
   for line in infile:
      match = re.match( r"(t[0-9a-f]+) +\[([ X-])\] +(\[([0-9-]+)\] +)?(.*)", line )
      if match:
         taskId = match[ 1 ]
         complete = match[ 2 ] == 'X'
         delete = match[ 2 ] == '-'
         date = match[ 4 ]
         title = match[ 5 ]

         task = taskById[ taskId ]
         if delete:
            task.delete()
         if complete:
            task.complete = True
            toSave.add( task )
         if task.title != title:
            task.title = title
            toSave.add( task )
         if task.project.title != project.title:
            if "due" in task.apiObject:
               print( "Warning: possible loss of time/repeat:",
                      task.lineString() )
            task.project = project
            toSave.add( task )
         # TODO edit task date?
      elif re.match( r"[A-Za-z0-9_]", line ):
         project = projectByName[ line.strip() ]
   for task in toSave:
      task.save()

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
