#!/usr/bin/env python3

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
import os.path
import pickle
import sys

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

   class Project( Project.Project ):
      def __init__( self, taskApi, apiObject  ):
         super().__init__( apiObject[ 'title' ] )
         self.loaded = False
         self.taskApi = taskApi
         self.apiObject = apiObject
         self.apiId = apiObject[ 'id' ]

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
            if self.apiObject[ key ] != value:
               self.apiObject[ key ] = value
               updated = True
         if updated:
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
            self.dueDate = apiObject[ 'due' ][ :10 ]
            if apiObject[ 'due' ][ 10: ] != "T00:00:00.000Z":
               self.dueTime = apiObject[ 'due' ][ 11: ]
               print( self.dueTime, file=sys.stderr )
         self.notes = apiObject.get( 'notes' )

      def print( self, options=None, outfile=sys.stdout ):
         if options and "debug" in options:
            print( "%s:" % self.shortId, self.apiObject, file=sys.stderr )
         super().print( options=options, outfile=outfile )

      def save( self ):
         status = "completed" if self.complete else "needsAction"
         apiMap = {
            'title': self.title,
            'status': status,
         }
         updated = False

         for key, value in apiMap.items():
            if self.apiObject.get( key ) != value:
               self.apiObject[ key ] = value
               updated = True

         if self.apiId is None or self.projectId != self.project.apiId:
            oldId = self.apiId
            oldProjectId = self.projectId
            self.projectId = self.project.apiId
            self.taskApi.tasks().insert(
                  tasklist=self.projectId,
                  body=self.apiObject ).execute()
            self.taskApi.invalidateProjectCache( self.projectId )
            if oldId is not None:
               self.taskApi.tasks().delete(
                     tasklist=oldProjectId,
                     task=oldId ).execute()
               self.taskApi.invalidateProjectCache( oldProjectId )
         elif updated:
            self.taskApi.tasks().update(
                  tasklist=self.projectId,
                  task=self.apiId,
                  body=self.apiObject ).execute()
            self.taskApi.invalidateProjectCache( self.projectId )

      def delete( self ):
         self.taskApi.tasks().delete(
               tasklist=self.projectId,
               task=self.apiId ).execute()
         self.taskApi.invalidateProjectCache( self.projectId )

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

   def tasklists( self ):
      return self.service.tasklists()

   def tasks( self ):
      return self.service.tasks()

   def getProjects( self ):
      first = True
      nextPage = None
      projects = []
      while nextPage or first:
         first = False
         result = self.service.tasklists().list( maxResults=100,
                                                 pageToken=nextPage ).execute()
         for apiObject in result.get( 'items', [] ):
            projects.append( GoogleTasks.Project( self, apiObject ) )
         nextPage = result.get( 'nextPageToken', None )
      updateShortIds( projects, "p" )
      return projects

   def addProject( self, project ):
      body = {
        "title": project.title,
      }
      apiObject = self.service.tasklists().insert( body=body ).execute()
      return GoogleTasks.Project( self.service, apiObject )

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
      self.allTasks |= newTasks
      updateShortIds( self.allTasks, "t" )
