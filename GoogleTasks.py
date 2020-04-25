#!/usr/bin/env python3

import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError

# API docs:
#   https://developers.google.com/api-client-library/python/
#   https://developers.google.com/tasks/get_started
#   https://developers.google.com/tasks/v1/reference/

import Project
from ShortId import updateShortIds
from Task import Task

class GoogleTasks:
   # If modifying these scopes, any pickled tokens will need removing
   # SCOPES = [ 'https://www.googleapis.com/auth/tasks.readonly' ]
   SCOPES = [ 'https://www.googleapis.com/auth/tasks' ]

   appCredentialsFileName = '/app-credentials.json'
   userCredentialsFileName = '/user-token.pickle'

   class Project( Project.Project ):
      def __init__( self, service, apiObject  ):
         super().__init__( apiObject[ 'title' ] )
         self.service = service
         self.apiObject = apiObject

      def save( self ):
         apiMap = {
            'title': self.title,
         }
         updated = False
         for key, value in apiMap.items():
            if self.apiObject[ key ] != value:
               self.apiObject[ key ] = value
               updated = True
         if updated:
            self.service.tasklists().update(
                  tasklist=self.apiObject[ 'id' ],
                      body=self.apiObject ).execute()

   def __init__( self, configDir, cacheDir ):
      self.creds = None
      self.service = None
      self.configDir = configDir
      self.cacheDir = cacheDir

   def authenticate( self ):
      self.creds = None

      appCredentialsFile = self.configDir + self.appCredentialsFileName
      userCredentialsFile = self.configDir + self.userCredentialsFileName

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

   def toTask( self, project, rawItem ):
      task = Task( project, rawItem[ 'title' ] )
      task.complete = rawItem[ 'status' ] == "completed"
      task.apiRef = self
      task.apiObject = rawItem
      return task

   def fromTask( self, task ):
      rawItem = task.apiObject
      rawItem[ 'title' ] = task.title
      rawItem[ 'status' ] = "completed" if task.complete else "needsAction"

   def getProjects( self ):
      first = True
      nextPage = None
      projects = []
      while nextPage or first:
         first = False
         result = self.service.tasklists().list( maxResults=100,
                                                 pageToken=nextPage ).execute()
         for apiObject in result.get( 'items', [] ):
            projects.append( GoogleTasks.Project( self.service, apiObject ) )
         nextPage = result.get( 'nextPageToken', None )
      updateShortIds( projects, "p" )
      return projects

   def addProject( self, project ):
      project = {
        "title": project.title,
      }
      apiObject = self.service.tasklists().insert( body=project ).execute()
      return GoogleTasks.Project( self.service, apiObject )

   def deleteProject( self, project ):
      projectId = project.apiObject[ 'id' ]
      self.service.tasklists().delete( tasklist=projectId ).execute()

   def updateTask( self, task ):
      self.fromTask( task )
      body = task.apiObject
      projectId = task.project.apiObject[ 'id' ]
      taskId = task.apiObject[ 'id' ]
      self.service.tasks().update( tasklist=projectId, task=taskId, body=body ).execute()

   def addTask( self, task ):
      task.apiObject = {}
      self.fromTask( task )
      body = task.apiObject
      projectId = task.project.apiObject[ 'id' ]
      self.service.tasks().insert( tasklist=projectId, body=body ).execute()

   def deleteTask( self, task ):
      self.fromTask( task )
      body = task.apiObject
      projectId = task.project.apiObject[ 'id' ]
      taskId = task.apiObject[ 'id' ]
      self.service.tasks().delete( tasklist=projectId, task=taskId ).execute()

   def moveTask( self, task, toProject ):
      self.fromTask( task )
      body = task.apiObject
      projectId = task.project.apiObject[ 'id' ]
      taskId = task.apiObject[ 'id' ]
      toProjectId = toProject.apiObject[ 'id' ]
      self.service.tasks().insert( tasklist=toProjectId, body=body ).execute()
      self.service.tasks().delete( tasklist=projectId, task=taskId ).execute()

   def invalidateCache( self, taskOrProject ):
      if isinstance( taskOrProject, Task ):
         projectId = taskOrProject.project.apiObject[ 'id' ]
      elif isinstance( taskOrProject, Project ):
         projectId = taskOrProject.apiObject[ 'id' ]
      else:
         assert False, "invalidateCache works on Task or Project only"
      # TODO - can we make it more fine-grained?
      projectCacheFile = self.cacheDir + ( '/project-%s.pickle' % projectId )
      taskCacheFile = self.cacheDir + ( '/tasks-%s.pickle' % projectId )
      if os.path.exists( projectCacheFile ):
         os.remove( projectCacheFile )
      if os.path.exists( taskCacheFile ):
         os.remove( taskCacheFile )

   def _getTasks( self, project ):
      projectId = project.apiObject[ 'id' ]
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
         for rawItem in result.get( 'items', [] ):
            tasks.append( self.toTask( project, rawItem ) )
         nextPage = result.get( 'nextPageToken', None )
      with open( taskCacheFile, 'wb' ) as taskCache:
         pickle.dump( tasks, taskCache )
      with open( projectCacheFile, 'wb' ) as projectCache:
         pickle.dump( project, projectCache )
      return tasks

   def getTasks( self, projects ):
      tasks = []
      for p in projects:
         tasks.extend( self._getTasks( p ) )
      updateShortIds( tasks, "t" )
      return tasks
