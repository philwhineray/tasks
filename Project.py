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
            print( "Matching...", task.shortId, task, file=sys.stderr )
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

   def parse( line ):
      match = re.match( r"^[*] \((p[0-9a-f]*)\) (.*)", line )
      if match:
         project = Project( match[ 2 ] )
         project.shortId = match[ 1 ]
         return project
      return None

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

      if ( "all" in options or
            "includeEmptyProjects" in options or
            ( criteria.match( project ) and
              criteria.hasInstanceOf( ProjectMatcher ) ) ):
         printProjectIfNeeded()

      sortKey = Task.Task.positionKey
      for task in sorted( project.tasks, key=sortKey ):
         if task.complete and "all" not in options:
            continue
         if criteria.match( task ):
            printProjectIfNeeded()
            task.print( options=options, outfile=outfile )

class ParseError( RuntimeError ):
   pass

def read( taskApi, options, infile=None ):
   projects = taskApi.getProjects()
   # Force reading of all tasks, so we get consistent short Ids.
   for project in Project.sort( projects ):
      _ = project.tasks

   projectTitles = set()
   projectById = {}
   taskById = {}
   for project in projects:
      projectById[ project.shortId ] = project
      projectTitles.add( project.title )
      for task in project.tasks:
         taskById[ task.shortId ] = task

   currentProject = None
   prevTask = None
   prevLevel = None
   lastInParent = {}
   tasksToDelete = set()
   projectsToDelete = set()
   projectsToSave = set()
   tasksToSave = []
   used = set()
   line = None
   lineNo = 0
   def readLine():
      nonlocal line, lineNo
      if not infile.readable():
         line = None
         return
      line = infile.readline()
      if line == '':
         line = None
         return
      lineNo += 1

   def isComment():
      if line is None:
         return False
      return re.match( "^\s*$", line ) or re.match( "^#", line )

   def parseComment():
      while isComment():
         readLine()

   def isTask():
      if line is None:
         return False
      return Task.Task.parse( currentProject, line ) is not None

   def parseTask():
      nonlocal prevTask, prevLevel
      if not currentProject:
         raise ParseError( "Line %d - task not in project: %s" % ( lineNo, line ) )
      task, isDeleted, level = Task.Task.parse( currentProject, line )
      if task is None:
         return
      errorLineNo = lineNo
      readLine()
      while ( line is not None and
              not isTask() and
              not isProject() ):
         if task.notes:
            task.notes += line
         else:
            task.notes = line
         readLine()
      if task.notes:
         task.notes = task.notes.strip()

      original = taskById.get( task.shortId )
      if not original:
         original = project.newTask()

      if original in used:
         raise ParseError( "Line %d - duplicate id: %s" % ( errorLineNo, original.shortId ) )
      used.add( original )

      if isDeleted:
         tasksToDelete.add( original )
         return

      original.title = task.title
      if "verbose" in options:
         original.notes = task.notes
      original.dueDate = task.dueDate
      original.complete = task.complete
      original.project = task.project

      if prevTask is None:
         if level != 0:
            raise ParseError( "Line %d - cannot start from level %d" % ( lineNo, level ) )
         original.parentTask = None
         posInParentKey = original.project
      elif level > prevTask.level() + 1:
         raise ParseError( "Line %d - cannot jump from level %d to %d" % ( lineNo, prevTask.level(), level ) )
      else:
         parent = prevTask
         parentLevel = parent.level()
         while parentLevel >= level:
            parent = parent.parentTask
            parentLevel -= 1
         levelBefore = original.level()
         original.parentTask = parent
         levelAfter = original.level()
         if levelAfter == 0:
            posInParentKey = original.project
         else:
            posInParentKey = parent

      predecessor = lastInParent.get( posInParentKey, None )
      predecessorId = predecessor.apiId if predecessor is not None else None
      original.previousTask = predecessor
      lastInParent[ posInParentKey ] = original

      prevTask = original
      prevLevel = original.level()

      tasksToSave.append( original )

   def isProject():
      if line is None:
         return False
      return Project.parse( line ) is not None

   def parseProject():
      nonlocal currentProject
      project = Project.parse( line )
      if project is None:
         return

      original = projectById.get( project.shortId )
      if not original:
         if project.title in projectTitles:
            raise ParseError( "Line %d - project %s already exists, refusing to duplicate name" % ( lineNo, project.title ) )
         original = taskApi.newProject()

      if original in used:
         raise ParseError( "Line %d - duplicate id: %s" % ( lineNo, original.shortId ) )
      used.add( original )

      if project.title == "-":
         projectsToDelete.add( original )
      else:
         original.title = project.title
         projectsToSave.add( original )
         currentProject = original

      readLine()
      if isComment():
         parseComment()
      while isTask():
         parseTask()

   def parseFile():
      readLine()
      if isComment():
         parseComment()

      while isProject():
         parseProject()

      if line and not isProject():
         raise ParseError( "Line %d - expected project, got: %s" % ( lineNo, line ) )

   parseFile()
   for project in projectsToDelete:
      if project.tasks:
         raise ParseError( "Project %s has tasks, refusing to delete" % project.shortId )

   for item in projectsToSave:
      item.save()
   for item in tasksToSave:
      item.save()
   for item in tasksToDelete:
      item.delete()
   for project in projectsToDelete:
      project.delete()

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
