#!/usr/bin/env python3

import re
import sys

import Matcher
import Task

class AmbiguousMatchError( RuntimeError ):
   pass

class Project:
   def __init__( self, title, accountName="default" ):
      self.shortId = None
      self.title = title
      self.accountName = accountName
      self._tasks = set()

   def get_displayName( self ):
      if self.accountName:
         return f"{self.accountName}:{self.title}"
      return self.title

   displayName = property( get_displayName )

   def save( self ):
      raise NotImplementedError( "must subclass Project.Project" )

   def delete( self ):
      raise NotImplementedError( "must subclass Project.Project" )

   def newTask( self ):
      raise NotImplementedError( "must subclass Project.Project" )

   def addTask( self, task ):
      self._tasks.add( task )

   def removeTask( self, task ):
      self._tasks.remove( task )

   def get_tasks( self ):
      return self._tasks

   tasks = property( get_tasks )

   def __str__( self ):
      shortIdStr = f"({self.shortId}) " if self.shortId else ""
      return f"* {shortIdStr}{self.displayName}"

   def print( self, options=None, outfile=None ):
      if outfile is None:
         outfile = sys.stdout
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

   def sort( projects, defaultAccount="default" ):
      def accountSorter( account ):
         if account == defaultAccount:
            return ( 0, "" )
         return ( 1, ( account or "" ).lower() )

      def titleSorter( name ):
         if name == "Scheduled":
            return ( 0, name )
         elif name == "Inbox":
            return ( 1, name )
         else:
            return ( 2, name.lower() if name else "" )

      return sorted(
         projects,
         key=lambda p: (
            accountSorter( getattr( p, "accountName", defaultAccount ) ),
            titleSorter( getattr( p, "title", "" ) )
         )
      )

   def parse( line, defaultAccount="default" ):
      match = re.match( r"^[*] \((p[0-9a-f]*)\) (.*)", line )
      if match:
         shortId = match[ 1 ]
         rest = match[ 2 ].strip()
         if ":" in rest:
            account, title = rest.split( ":", 1 )
            account = account.strip()
            title = title.strip()
         else:
            account = defaultAccount
            title = rest
         project = Project( title, accountName=account )
         project.shortId = shortId
         return project
      return None

def write( projects, options, criteria, outfile=None ):
   if outfile is None:
      outfile = sys.stdout
   printedProject = set()
   defaultAccount = "default"
   if projects:
      first = next( iter( projects ) )
      if hasattr( first, "taskApi" ) and hasattr( first.taskApi, "defaultAccountName" ):
         defaultAccount = first.taskApi.defaultAccountName
      elif hasattr( first, "taskApi" ) and hasattr( getattr( first.taskApi, "manager", None ), "defaultAccountName" ):
         defaultAccount = first.taskApi.manager.defaultAccountName

   sortedProjects = Project.sort( projects, defaultAccount=defaultAccount )

   # Force reading of all tasks, so we get consistent short Ids.
   for project in sortedProjects:
      _ = project.tasks

   for project in sortedProjects:

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
   defaultAccount = getattr( taskApi, "defaultAccountName", "default" )

   # Force reading of all tasks, so we get consistent short Ids.
   for project in Project.sort( projects, defaultAccount=defaultAccount ):
      _ = project.tasks

   projectKeys = set()
   projectById = {}
   taskById = {}
   for project in projects:
      projectById[ project.shortId ] = project
      acct = getattr( project, "accountName", defaultAccount )
      projectKeys.add( ( acct, project.title ) )
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
   crossAccountMigrated = {}
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
      return re.match( r"^\s*$", line ) or re.match( r"^#", line )

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
         targetTask = currentProject.newTask()
      else:
         if original in used:
            raise ParseError( "Line %d - duplicate id: %s" % ( errorLineNo, original.shortId ) )
         used.add( original )

         if isDeleted:
            tasksToDelete.add( original )
            return

         origAccount = getattr( original, "accountName", getattr( original.project, "accountName", defaultAccount ) )
         targetAccount = getattr( currentProject, "accountName", defaultAccount )

         if origAccount != targetAccount:
            targetTask = currentProject.newTask()
            tasksToDelete.add( original )
            crossAccountMigrated[ original ] = targetTask
         else:
            targetTask = original
            targetTask.project = currentProject

      targetTask.title = task.title
      if "verbose" in options:
         targetTask.notes = task.notes
      elif original and hasattr( original, "notes" ):
         targetTask.notes = original.notes
      targetTask.dueDate = task.dueDate
      targetTask.complete = task.complete

      if prevTask is None:
         if level != 0:
            raise ParseError( "Line %d - cannot start from level %d" % ( lineNo, level ) )
         targetTask.parentTask = None
         posInParentKey = targetTask.project
      elif level > prevTask.level() + 1:
         raise ParseError( "Line %d - cannot jump from level %d to %d" % ( lineNo, prevTask.level(), level ) )
      else:
         parent = prevTask
         parentLevel = parent.level()
         while parentLevel >= level:
            parent = parent.parentTask
            parentLevel -= 1
         targetTask.parentTask = parent
         if targetTask.level() == 0:
            posInParentKey = targetTask.project
         else:
            posInParentKey = parent

      predecessor = lastInParent.get( posInParentKey, None )
      targetTask.previousTask = predecessor
      lastInParent[ posInParentKey ] = targetTask

      prevTask = targetTask
      prevLevel = targetTask.level()

      tasksToSave.append( targetTask )

   def isProject():
      if line is None:
         return False
      return Project.parse( line, defaultAccount=defaultAccount ) is not None

   def parseProject():
      nonlocal currentProject
      project = Project.parse( line, defaultAccount=defaultAccount )
      if project is None:
         return

      original = projectById.get( project.shortId )
      if not original:
         if ( project.accountName, project.title ) in projectKeys:
            raise ParseError( "Line %d - project %s:%s already exists, refusing to duplicate name" % ( lineNo, project.accountName, project.title ) )
         if hasattr( taskApi, "newProject" ):
            try:
               original = taskApi.newProject( accountName=project.accountName )
            except TypeError:
               original = taskApi.newProject()
         else:
            original = taskApi.newProject()
         original.title = project.title
         if hasattr( original, "accountName" ):
            original.accountName = project.accountName
         projectKeys.add( ( project.accountName, project.title ) )
      else:
         origAccount = getattr( original, "accountName", defaultAccount )
         if origAccount != project.accountName:
            raise ParseError( "Line %d - changing project account from '%s' to '%s' is not supported (project %s)" % ( lineNo, origAccount, project.accountName, project.shortId ) )

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

   def migrateChildren( oldParent, newParent ):
      for child in sorted( getattr( oldParent, "childTasks", [] ), key=Task.Task.positionKey ):
         if child not in used and child not in tasksToDelete:
            migratedChild = newParent.project.newTask()
            migratedChild.title = child.title
            migratedChild.notes = getattr( child, "notes", None )
            migratedChild.dueDate = getattr( child, "dueDate", None )
            migratedChild.dueTime = getattr( child, "dueTime", None )
            migratedChild.complete = getattr( child, "complete", False )
            migratedChild.parentTask = newParent
            tasksToSave.append( migratedChild )
            tasksToDelete.add( child )
            migrateChildren( child, migratedChild )

   for origTask, newParent in crossAccountMigrated.items():
      migrateChildren( origTask, newParent )

   for project in projectsToDelete:
      remainingTasks = [ t for t in project.tasks if t not in tasksToDelete ]
      if remainingTasks:
         raise ParseError( "Project %s has tasks, refusing to delete" % project.shortId )

   for item in projectsToSave:
      item.save()
   for item in tasksToSave:
      item.save()
   for item in tasksToDelete:
      try:
         item.delete()
      except Exception as ex:
         print( "Warning: failed to delete source task %s: %s" % ( getattr( item, "shortId", "" ), ex ), file=sys.stderr )
         raise
   for project in projectsToDelete:
      project.delete()

   if hasattr( taskApi, "assignShortIds" ):
      taskApi.assignShortIds()

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
         project = getattr( projectOrTask, "project", None )
         if project is None:
            return False

      if self.word == project.shortId:
         result = True
      elif ":" in self.word:
         acctPart, titlePart = self.word.split( ":", 1 )
         projectAcct = getattr( project, "accountName", "" ) or ""
         acctMatch = ( projectAcct.lower() == acctPart.lower() )
         titleMatch = ( titlePart == project.shortId or
                        bool( re.search( titlePart, project.title or "", flags=re.IGNORECASE ) ) )
         result = acctMatch and titleMatch
      else:
         result = bool( re.search( self.word, project.title or "", flags=re.IGNORECASE ) )

      if self.debug:
         if result:
            print( "Project.Word", "match", file=sys.stderr )
         else:
            print( "Project.Word", "no match", file=sys.stderr )
      return result
