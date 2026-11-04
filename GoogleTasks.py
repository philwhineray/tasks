#!/usr/bin/env python3

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
import os
import os.path
import pickle
import shutil
import sys
import time

# API docs:
#   https://developers.google.com/api-client-library/python/
#   https://developers.google.com/tasks/get_started
#   https://developers.google.com/tasks/v1/reference/

import Project
from ShortId import updateShortIds
import Task

class GoogleTasks:
   # If modifying these scopes, any pickled tokens will need removing
   # SCOPES = [ 'https://www.googleapis.com/auth/tasks.readonly' ]
   SCOPES = [ 'https://www.googleapis.com/auth/tasks' ]

   appCredentialsFileName = '/app-credentials.json'
   userCredentialsFileName = '/user-token.pickle'
   allTasks = set()
   projects = None

   def fromApiTime( dateTime ):
      date = dateTime[ :10 ]
      if dateTime[ 10: ] != "T00:00:00.000Z":
         return date, dateTime[ 11:-8 ]
      else:
         return date, None

   def toApiTime( date, time ):
      if not date:
         return None
      if not time:
         time = "00:00"
      return date + "T" + time + ":00.000Z"

   class Project( Project.Project ):
      def __init__( self, taskApi, apiObject ):
         super().__init__( apiObject.get( 'title' ), accountName=taskApi.accountName )
         self.loaded = False
         self.taskApi = taskApi
         self.apiObject = apiObject
         self.apiId = apiObject.get( 'id' )

      def print( self, options=None, outfile=sys.stdout ):
         if options and "debug" in options:
            print( "%s:" % self.shortId, self.apiObject, file=sys.stderr )
         super().print( options=options, outfile=outfile )

      def save( self ):
         apiMap = {
            'title': self.title,
         }
         updated = False
         for key, value in apiMap.items():
            original = self.apiObject.get( key )
            if original != value:
               self.apiObject[ key ] = value
               updated = True

         if self.apiId is None:
            self.apiObject = self.taskApi.tasklists().insert(
                  body=self.apiObject ).execute()
            self.apiId = self.apiObject[ 'id' ]
         elif updated:
            self.taskApi.tasklists().update(
                  tasklist=self.apiId,
                  body=self.apiObject ).execute()
            self.taskApi.invalidateProjectCache( self.apiId )

      def delete( self ):
         self.taskApi.tasklists().delete(
               tasklist=self.apiId ).execute()
         self.taskApi.invalidateProjectCache( self.apiId )

      def get_tasks( self ):
         if not self.loaded:
            self.loaded = True
            for apiObject in self.taskApi._getRawTasks( self ):
               GoogleTasks.Task( self, apiObject )
            self.taskApi.assignTaskIds( self._tasks )
            taskById = {}
            for task in self._tasks:
               taskById[ task.apiId ] = task
            previousByParentId = {}
            for task in sorted( self._tasks, key=Task.Task.positionKey ):
               parentId = task.apiObject.get( 'parent', task.project.apiId  )
               task.parentTask = taskById.get( parentId )
               predecessorId = previousByParentId.get( parentId )
               previousTask = taskById.get( predecessorId )
               if previousTask is None:
                  task.previousTask = None
                  task.predecessorId = None
               else:
                  task.previousTask = previousTask
                  task.predecessorId = predecessorId
               if not task.complete:
                  previousByParentId[ parentId ] = task.apiId
         return super().get_tasks()

      tasks = property( get_tasks )

      def newTask( self ):
         return GoogleTasks.Task( self, {} )

   class Task( Task.Task ):
      def __init__( self, project, apiObject ):
         if not isinstance( project, GoogleTasks.Project ):
            raise RuntimeError( "cannot add Google Task to non-Google project" )
         super().__init__( project )
         self.project = project
         self.taskApi = project.taskApi
         self.projectId = self.project.apiId
         self.apiObject = apiObject
         self.title = apiObject.get( 'title' )
         self.apiId = apiObject.get( 'id' )
         self.complete = apiObject.get( 'status' ) == "completed"
         if 'due' in apiObject:
            self.dueDate, self.dueTime = GoogleTasks.fromApiTime(
                  apiObject[ 'due' ] )
         self.notes = apiObject.get( 'notes' )
         # These get set up when read in bulk
         self.predecessorId = None
         self.previousTask = None

      def apiOrderKey( self ):
         return int( self.apiObject.get( 'position', '0' ) )

      def print( self, options=None, outfile=sys.stdout ):
         if options and "debug" in options:
            print( "%s:" % self.shortId, self.apiObject, file=sys.stderr )
         super().print( options=options, outfile=outfile )

      def save( self ):
         status = "completed" if self.complete else "needsAction"
         due = GoogleTasks.toApiTime( self.dueDate, self.dueTime )
         apiMap = {
            'title': self.title,
            'status': status,
            'notes': self.notes,
            'due': due,
         }
         updated = False

         for key, value in apiMap.items():
            original = self.apiObject.get( key )
            if original != value:
               if value is None:
                  del self.apiObject[ key ]
               else:
                  self.apiObject[ key ] = value
               updated = True
               if key == "due" and original is not None and value is not None:
                  print( "Warning: possible loss of time/repeat:",
                         self, file=sys.stderr )

         if self.apiId is None or self.projectId != self.project.apiId:
            oldId = self.apiId
            oldProjectId = self.projectId
            self.projectId = self.project.apiId
            self.apiObject = self.executeWithRetry(
                                self.taskApi.tasks().insert,
                                tasklist=self.projectId,
                                body=self.apiObject )
            self.apiId = self.apiObject[ 'id' ]
            self.taskApi.invalidateProjectCache( self.projectId )
            if oldId is not None:
               self.executeWithRetry( self.taskApi.tasks().delete,
                     tasklist=oldProjectId,
                     task=oldId )
               self.taskApi.invalidateProjectCache( oldProjectId )
         elif updated:
            self.executeWithRetry( self.taskApi.tasks().update,
                  tasklist=self.projectId,
                  task=self.apiId,
                  body=self.apiObject )
            self.taskApi.invalidateProjectCache( self.projectId )

         parentId = None if self.parentTask is None else self.parentTask.apiId
         predecessorId = None if self.previousTask is None else self.previousTask.apiId
         if self.apiObject.get( 'parent' ) != parentId or self.predecessorId != predecessorId:
            moveParam = {
                  'tasklist': self.projectId,
                  'task': self.apiId,
            }
            if parentId is not None:
               moveParam[ 'parent' ] = parentId
            if predecessorId is not None:
               moveParam[ 'previous' ] = predecessorId
            self.executeWithRetry( self.taskApi.tasks().move,
                                   **moveParam )
            self.taskApi.invalidateProjectCache( self.projectId )

      def delete( self ):
         self.executeWithRetry( self.taskApi.tasks().delete,
               tasklist=self.projectId,
               task=self.apiId )
         self.taskApi.invalidateProjectCache( self.projectId )

      def executeWithRetry( self, fn, **params ):
         maxRetry = 10
         retriesRemaining = maxRetry
         result = None
         while retriesRemaining:
            retriesRemaining -= 1
            try:
               result = fn( **params ).execute()
               lastException = None
            except Exception as e:
               lastException = e
               time.sleep( maxRetry - retriesRemaining )
            else:
               break
         if lastException is not None:
            raise lastException
         return result


   def __init__( self, configDir, cacheDir, accountName="default" ):
      self.creds = None
      self.service = None
      self.configDir = configDir
      self.accountName = accountName
      self.cacheDir = os.path.join( cacheDir, accountName )
      self.manager = None
      if not os.path.exists( self.cacheDir ):
         os.makedirs( self.cacheDir )

   def authenticate( self, alternateCredentials=None ):
      self.creds = None

      if alternateCredentials:
         suffix = "." + alternateCredentials
      elif self.accountName and self.accountName != "default":
         suffix = "." + self.accountName
      else:
         suffix = ""

      appCredentialsFile = self.configDir + self.appCredentialsFileName + suffix
      userCredentialsFile = self.configDir + self.userCredentialsFileName + suffix

      if self.accountName == "default" and not os.path.exists( appCredentialsFile ):
         if os.path.exists( appCredentialsFile + ".default" ):
            appCredentialsFile = appCredentialsFile + ".default"
            userCredentialsFile = userCredentialsFile + ".default"

      if not os.path.exists( appCredentialsFile ):
         raise RuntimeError( "no credentials file", appCredentialsFile )

      # The userCredentialsFile stores the user's access and refresh tokens,
      # and is created automatically when the authorization flow completes
      # for the first time.
      if os.path.exists( userCredentialsFile ):
         with open( userCredentialsFile, 'rb' ) as token:
            self.creds = pickle.load( token )

      # If there are no (valid) credentials available, let the user log in.
      if not self.creds or not self.creds.valid:
         authenticated = False
         if self.creds and self.creds.expired and self.creds.refresh_token:
            try:
               self.creds.refresh( Request() )
               authenticated = True
            except:
               pass
         if not authenticated:
            flow = InstalledAppFlow.from_client_secrets_file(
                      appCredentialsFile, GoogleTasks.SCOPES )
            self.creds = flow.run_local_server()
            # Save the credentials for the next run
            with open( userCredentialsFile, 'wb' ) as token:
               pickle.dump( self.creds, token )

      self.service = build( 'tasks', 'v1', credentials=self.creds )

   def tasklists( self ):
      return self.service.tasklists()

   def tasks( self ):
      return self.service.tasks()

   def getProjects( self, updateIds=True ):
      first = True
      nextPage = None
      self.projects = []
      self.allTasks = set()
      while nextPage or first:
         first = False
         result = self.service.tasklists().list( maxResults=100,
                                                 pageToken=nextPage ).execute()
         for apiObject in result.get( 'items', [] ):
            self.projects.append( GoogleTasks.Project( self, apiObject ) )
         nextPage = result.get( 'nextPageToken', None )
      if updateIds:
         updateShortIds( self.projects, "p" )
      return self.projects

   def newProject( self ):
      return GoogleTasks.Project( self, {} )

   def invalidateProjectCache( self, projectId ):
      # TODO - can we make it more fine-grained?
      # TODO - can we make it save back, rather than reload each time?
      projectCacheFile = self.cacheDir + ( '/project-%s.pickle' % projectId )
      taskCacheFile = self.cacheDir + ( '/tasks-%s.pickle' % projectId )
      if os.path.exists( projectCacheFile ):
         os.remove( projectCacheFile )
      if os.path.exists( taskCacheFile ):
         os.remove( taskCacheFile )

   def _getRawTasks( self, project ):
      projectId = project.apiId
      updated = project.apiObject[ 'updated' ]
      projectCacheFile = self.cacheDir + ( '/project-%s.pickle' % projectId )
      taskCacheFile = self.cacheDir + ( '/tasks-%s.pickle' % projectId )
      if os.path.exists( projectCacheFile ) and os.path.exists( taskCacheFile ):
         with open( projectCacheFile, 'rb' ) as projectCache:
            cachedProject = pickle.load( projectCache )
            if cachedProject.apiObject[ 'updated' ] >= project.apiObject[ 'updated' ]:
               with open( taskCacheFile, 'rb' ) as taskCache:
                  tasks = pickle.load( taskCache )
                  return tasks
      first = True
      nextPage = None
      tasks = []
      while nextPage or first:
         first = False
         result = self.service.tasks().list( maxResults=100, tasklist=projectId,
                                             pageToken=nextPage, showHidden=True,
                                             showCompleted=True ).execute()
         items = result.get( 'items', [] )
         tasks.extend( items )
         nextPage = result.get( 'nextPageToken', None )
      with open( taskCacheFile, 'wb' ) as taskCache:
         pickle.dump( tasks, taskCache )
      with open( projectCacheFile, 'wb' ) as projectCache:
         pickle.dump( project, projectCache )
      return tasks

   def assignTaskIds( self, newTasks ):
      if self.manager is not None:
         self.manager.assignTaskIds( newTasks )
      else:
         self.allTasks |= newTasks
         updateShortIds( self.allTasks, "t" )

class MultiAccountManager:
   """Manages multiple GoogleTasks adapter instances across accounts."""

   def __init__( self, configDir, cacheDir, activeAccount=None ):
      self.configDir = configDir
      self.cacheDir = cacheDir
      self.activeAccount = activeAccount  # None = all accounts; str = single override
      self.accounts = {}
      self.defaultAccountName = "default"
      self.allTasks = set()
      self.allProjects = []
      self._discoverAccounts()
      self._authenticateAll()

   def _discoverAccounts( self ):
      """Scans configDir for app-credentials.json* and default-account."""
      if not os.path.exists( self.configDir ):
         raise RuntimeError( "Config directory does not exist", self.configDir )

      discovered = {}
      defaultCred = os.path.join( self.configDir, "app-credentials.json" )
      if os.path.exists( defaultCred ):
         discovered[ "default" ] = defaultCred

      prefix = "app-credentials.json."
      for fname in sorted( os.listdir( self.configDir ) ):
         if fname.startswith( prefix ):
            acctName = fname[ len( prefix ): ]
            if acctName:
               discovered[ acctName ] = os.path.join( self.configDir, fname )

      if not discovered:
         raise RuntimeError( "no credentials file - see README.md#app-authentication", defaultCred )

      # Check default-account file
      defaultAccountFile = os.path.join( self.configDir, "default-account" )
      hasDefaultAccountFile = False
      if os.path.exists( defaultAccountFile ):
         with open( defaultAccountFile, "r" ) as f:
            for line in f:
               line = line.strip()
               if line and not line.startswith( "#" ):
                  self.defaultAccountName = line
                  hasDefaultAccountFile = True
                  break

      if self.defaultAccountName not in discovered:
         if len( discovered ) == 1 and not hasDefaultAccountFile:
            self.defaultAccountName = next( iter( discovered.keys() ) )
         else:
            raise RuntimeError(
               f"Default account '{self.defaultAccountName}' not found in discovered accounts: {list( discovered.keys() )}"
            )

      if self.activeAccount:
         if self.activeAccount not in discovered:
            raise RuntimeError(
               f"Specified account '{self.activeAccount}' not found in discovered accounts: {list( discovered.keys() )}"
            )
         self.activeAccountNames = [ self.activeAccount ]
      else:
         self.activeAccountNames = list( discovered.keys() )

      self.discoveredAccounts = discovered

   def _migrateLegacyCache( self ):
      """Migrates ~/.cache/tasks/*.pickle into ~/.cache/tasks/default/."""
      if not os.path.exists( self.cacheDir ):
         return
      defaultCacheDir = os.path.join( self.cacheDir, "default" )
      for fname in os.listdir( self.cacheDir ):
         if fname.endswith( ".pickle" ) and ( fname.startswith( "project-" ) or fname.startswith( "tasks-" ) ):
            if not os.path.exists( defaultCacheDir ):
               os.makedirs( defaultCacheDir )
            oldPath = os.path.join( self.cacheDir, fname )
            newPath = os.path.join( defaultCacheDir, fname )
            try:
               shutil.move( oldPath, newPath )
            except Exception:
               pass

   def _authenticateAll( self ):
      """Authenticates each active account adapter."""
      self._migrateLegacyCache()
      authErrors = []
      for name in self.activeAccountNames:
         try:
            gt = GoogleTasks( self.configDir, self.cacheDir, accountName=name )
            gt.manager = self
            gt.authenticate()
            self.accounts[ name ] = gt
         except Exception as e:
            authErrors.append( ( name, e ) )
            print( f"Warning: failed to authenticate account '{name}': {e}", file=sys.stderr )

      if not self.accounts:
         if authErrors:
            raise authErrors[ 0 ][ 1 ]
         else:
            raise RuntimeError( "No accounts available" )

   def getProjects( self ):
      """Fetches and aggregates projects across all accounts with global ShortIds."""
      self.allProjects = []
      for name, acct in self.accounts.items():
         acctProjects = acct.getProjects( updateIds=False )
         self.allProjects.extend( acctProjects )
      self.allProjects = Project.Project.sort( self.allProjects, defaultAccount=self.defaultAccountName )
      updateShortIds( self.allProjects, "p" )
      return self.allProjects

   def newProject( self, accountName=None ):
      """Creates a new Project attached to the specified or default account."""
      if accountName is None:
         accountName = self.defaultAccountName
      if accountName not in self.accounts:
         raise RuntimeError( f"Account '{accountName}' not found in active accounts: {list( self.accounts.keys() )}" )
      return self.accounts[ accountName ].newProject()

   def assignTaskIds( self, newTasks ):
      """Recomputes global collision-free ShortIds across all loaded tasks."""
      self.allTasks |= set( newTasks )
      updateShortIds( self.allTasks, "t" )

   def assignShortIds( self ):
      """Recomputes global collision-free ShortIds across all projects and tasks."""
      if self.allProjects:
         updateShortIds( self.allProjects, "p" )
      if self.allTasks:
         updateShortIds( self.allTasks, "t" )

