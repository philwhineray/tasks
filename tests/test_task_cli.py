import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path
import unittest

import Matcher
import Project
import Task

task_path = Path( __file__ ).parent.parent / "task"
loader = SourceFileLoader( "task_cli", str( task_path ) )
spec = importlib.util.spec_from_loader( "task_cli", loader )
task_cli = importlib.util.module_from_spec( spec )
loader.exec_module( task_cli )


class MockTask:
   def __init__( self, project ):
      self.project = project
      self.title = None
      self.saved = False

   def save( self ):
      self.saved = True


class MockProject( Project.Project ):
   def __init__( self, title, shortId="p01" ):
      super().__init__( title )
      self.shortId = shortId
      self.apiObject = {}
      self.created_task = None

   def newTask( self ):
      self.created_task = MockTask( self )
      return self.created_task


class MockTaskApi:
   def __init__( self, projects ):
      self._projects = list( projects )

   def getProjects( self ):
      return self._projects


class TestDoTaskAdd( unittest.TestCase ):
   def test_do_task_add_success( self ):
      project = MockProject( "Inbox" )
      api = MockTaskApi( [ project ] )
      criteria = Matcher.And()
      criteria.add( Project.WordMatcher( "Inbox" ) )

      task_cli.doTaskAdd( api, {}, criteria, [ "Buy", "groceries" ], {} )

      self.assertIsNotNone( project.created_task )
      self.assertEqual( project.created_task.title, "Buy groceries" )
      self.assertTrue( project.created_task.saved )

   def test_do_task_add_with_task_matcher_raises( self ):
      project = MockProject( "Inbox" )
      api = MockTaskApi( [ project ] )
      criteria = Matcher.And()
      criteria.add( Task.WordMatcher( "groceries" ) )

      with self.assertRaises( RuntimeError ) as ctx:
         task_cli.doTaskAdd( api, {}, criteria, [ "Buy", "groceries" ], {} )
      self.assertIn( "Cannot use task criteria", str( ctx.exception ) )

   def test_do_task_add_multiple_projects_raises( self ):
      p1 = MockProject( "Inbox", "p01" )
      p2 = MockProject( "Work", "p02" )
      api = MockTaskApi( [ p1, p2 ] )
      criteria = Matcher.And()

      with self.assertRaises( RuntimeError ) as ctx:
         task_cli.doTaskAdd( api, {}, criteria, [ "Buy", "groceries" ], {} )
      self.assertIn( "Matched 2 project(s)", str( ctx.exception ) )

   def test_do_task_add_no_matching_project_raises( self ):
      p1 = MockProject( "Inbox", "p01" )
      api = MockTaskApi( [ p1 ] )
      criteria = Matcher.And()
      criteria.add( Project.WordMatcher( "Nonexistent" ) )

      with self.assertRaises( RuntimeError ) as ctx:
         task_cli.doTaskAdd( api, {}, criteria, [ "Buy", "groceries" ], {} )
      self.assertIn( "Matched 0 project(s)", str( ctx.exception ) )


if __name__ == '__main__':
   unittest.main()
