import importlib.util
from importlib.machinery import SourceFileLoader
import io
from pathlib import Path
import sys
import unittest

import Matcher
import Project
import Task

task_path = Path( __file__ ).parent.parent / "task"
loader = SourceFileLoader( "task_cli", str( task_path ) )
spec = importlib.util.spec_from_loader( "task_cli", loader )
task_cli = importlib.util.module_from_spec( spec )
loader.exec_module( task_cli )


class MockCLITask( Task.Task ):
   def __init__( self, project, title="Task", shortId=None, complete=False ):
      super().__init__( project )
      self.title = title
      self.shortId = shortId
      self.complete = complete
      self.saved = False
      self.deleted = False

   def apiOrderKey( self ):
      return 0

   def save( self ):
      self.saved = True

   def delete( self ):
      self.deleted = True


class MockCLIProject( Project.Project ):
   def __init__( self, title, accountName="default", shortId=None ):
      super().__init__( title, accountName=accountName )
      self.shortId = shortId
      self.saved = False
      self.deleted = False
      self.createdTask = None

   def save( self ):
      self.saved = True

   def delete( self ):
      self.deleted = True

   def newTask( self ):
      self.createdTask = MockCLITask( self )
      return self.createdTask


class MockCLIAccountManager:
   def __init__( self, defaultAccountName="default", projects=None ):
      self.defaultAccountName = defaultAccountName
      self._projects = list( projects ) if projects else []
      self.accounts = {}
      for p in self._projects:
         if p.accountName not in self.accounts:
            self.accounts[ p.accountName ] = []
         self.accounts[ p.accountName ].append( p )

   def getProjects( self ):
      return list( self._projects )

   def newProject( self, accountName=None ):
      if accountName is None:
         accountName = self.defaultAccountName
      p = MockCLIProject( "", accountName=accountName )
      self._projects.append( p )
      return p


class TestCLIScenarios( unittest.TestCase ):
   def test_unified_listing( self ):
      p_def = MockCLIProject( "Inbox", accountName="default", shortId="p01" )
      p_work = MockCLIProject( "Inbox", accountName="work", shortId="p02" )
      t1 = MockCLITask( p_def, "Def task", shortId="t01" )
      t2 = MockCLITask( p_work, "Work task", shortId="t02" )

      api = MockCLIAccountManager( defaultAccountName="default", projects=[ p_work, p_def ] )

      old_stdout = sys.stdout
      sys.stdout = io.StringIO()
      try:
         task_cli.doTaskList( api, {}, Matcher.And(), [], {} )
         output = sys.stdout.getvalue()
      finally:
         sys.stdout = old_stdout

      # Projects should be listed with account prefixes
      self.assertIn( "* (p01) default:Inbox", output )
      self.assertIn( "** (t01) [ ] Def task", output )
      self.assertIn( "* (p02) work:Inbox", output )
      self.assertIn( "** (t02) [ ] Work task", output )

      # Check default account appears before work account in output
      pos_def = output.find( "default:Inbox" )
      pos_work = output.find( "work:Inbox" )
      self.assertLess( pos_def, pos_work )

   def test_individual_action_without_project_or_account( self ):
      p_work = MockCLIProject( "Inbox", accountName="work", shortId="p01" )
      t_work = MockCLITask( p_work, "Fix prod bug", shortId="t12", complete=False )

      api = MockCLIAccountManager( defaultAccountName="default", projects=[ p_work ] )

      # doTaskDone with task shortId 't12'
      criteria = Matcher.And()
      criteria.add( Task.WordMatcher( "t12" ) )

      old_stdout = sys.stdout
      sys.stdout = io.StringIO()
      try:
         task_cli.doTaskDone( api, {}, criteria, [], {} )
      finally:
         sys.stdout = old_stdout

      self.assertTrue( t_work.complete )
      self.assertTrue( t_work.saved )

      # Now doTaskUndo
      criteria = Matcher.And()
      criteria.add( Task.WordMatcher( "t12" ) )
      sys.stdout = io.StringIO()
      try:
         task_cli.doTaskUndo( api, {}, criteria, [], {} )
      finally:
         sys.stdout = old_stdout

      self.assertFalse( t_work.complete )

      # Now doTaskDelete
      criteria = Matcher.And()
      criteria.add( Task.WordMatcher( "t12" ) )
      sys.stdout = io.StringIO()
      try:
         task_cli.doTaskDelete( api, {}, criteria, [], {} )
      finally:
         sys.stdout = old_stdout

      self.assertTrue( t_work.deleted )

   def test_add_task_unqualified_project_resolves_to_default_account( self ):
      p_def = MockCLIProject( "Inbox", accountName="default", shortId="p01" )
      p_work = MockCLIProject( "Inbox", accountName="work", shortId="p02" )
      api = MockCLIAccountManager( defaultAccountName="default", projects=[ p_def, p_work ] )

      criteria = Matcher.And()
      criteria.add( Project.WordMatcher( "Inbox" ) )

      task_cli.doTaskAdd( api, {}, criteria, [ "Buy", "groceries" ], {} )

      self.assertIsNotNone( p_def.createdTask )
      self.assertEqual( p_def.createdTask.title, "Buy groceries" )
      self.assertTrue( p_def.createdTask.saved )
      self.assertIsNone( p_work.createdTask )

   def test_add_task_qualified_project( self ):
      p_def = MockCLIProject( "Inbox", accountName="default", shortId="p01" )
      p_work = MockCLIProject( "Inbox", accountName="work", shortId="p02" )
      api = MockCLIAccountManager( defaultAccountName="default", projects=[ p_def, p_work ] )

      criteria = Matcher.And()
      criteria.add( Project.WordMatcher( "work:Inbox" ) )

      task_cli.doTaskAdd( api, {}, criteria, [ "Deploy", "release" ], {} )

      self.assertIsNone( p_def.createdTask )
      self.assertIsNotNone( p_work.createdTask )
      self.assertEqual( p_work.createdTask.title, "Deploy release" )
      self.assertTrue( p_work.createdTask.saved )

   def test_project_rename_ambiguous_across_accounts_raises( self ):
      p_def = MockCLIProject( "Inbox", accountName="default", shortId="p01" )
      p_work = MockCLIProject( "Inbox", accountName="work", shortId="p02" )
      api = MockCLIAccountManager( defaultAccountName="default", projects=[ p_def, p_work ] )

      criteria = Matcher.And()
      criteria.add( Project.WordMatcher( "Inbox" ) )

      with self.assertRaises( Project.AmbiguousMatchError ) as ctx:
         task_cli.doProjectRename( api, {}, criteria, [ "NewInbox" ], {} )

      msg = str( ctx.exception )
      self.assertIn( "matches projects across multiple accounts", msg )
      self.assertIn( "default:Inbox (p01)", msg )
      self.assertIn( "work:Inbox (p02)", msg )

   def test_project_rename_qualified_success( self ):
      p_def = MockCLIProject( "Inbox", accountName="default", shortId="p01" )
      p_work = MockCLIProject( "Inbox", accountName="work", shortId="p02" )
      api = MockCLIAccountManager( defaultAccountName="default", projects=[ p_def, p_work ] )

      criteria = Matcher.And()
      criteria.add( Project.WordMatcher( "work:Inbox" ) )

      task_cli.doProjectRename( api, {}, criteria, [ "WorkInbox" ], {} )

      self.assertEqual( p_work.title, "WorkInbox" )
      self.assertTrue( p_work.saved )
      self.assertEqual( p_def.title, "Inbox" )

   def test_project_delete_ambiguous_across_accounts_raises( self ):
      p_def = MockCLIProject( "Inbox", accountName="default", shortId="p01" )
      p_work = MockCLIProject( "Inbox", accountName="work", shortId="p02" )
      api = MockCLIAccountManager( defaultAccountName="default", projects=[ p_def, p_work ] )

      criteria = Matcher.And()
      criteria.add( Project.WordMatcher( "Inbox" ) )

      with self.assertRaises( Project.AmbiguousMatchError ) as ctx:
         task_cli.doProjectDelete( api, { "force": True }, criteria, [], {} )

      msg = str( ctx.exception )
      self.assertIn( "matches projects across multiple accounts", msg )
      self.assertFalse( p_def.deleted )
      self.assertFalse( p_work.deleted )

   def test_project_delete_by_short_id_unambiguous( self ):
      p_def = MockCLIProject( "Inbox", accountName="default", shortId="p01" )
      p_work = MockCLIProject( "Inbox", accountName="work", shortId="p02" )
      api = MockCLIAccountManager( defaultAccountName="default", projects=[ p_def, p_work ] )

      criteria = Matcher.And()
      criteria.add( Project.WordMatcher( "p02" ) )

      old_stderr = sys.stderr
      sys.stderr = io.StringIO()
      try:
         task_cli.doProjectDelete( api, { "force": True }, criteria, [], {} )
      finally:
         sys.stderr = old_stderr

      self.assertFalse( p_def.deleted )
      self.assertTrue( p_work.deleted )

   def test_project_add_default_account( self ):
      api = MockCLIAccountManager( defaultAccountName="default" )
      task_cli.doProjectAdd( api, {}, Matcher.And(), [ "NewProject" ], {} )

      projects = api.getProjects()
      self.assertEqual( len( projects ), 1 )
      self.assertEqual( projects[ 0 ].accountName, "default" )
      self.assertEqual( projects[ 0 ].title, "NewProject" )
      self.assertTrue( projects[ 0 ].saved )

   def test_project_add_with_account_in_title( self ):
      api = MockCLIAccountManager( defaultAccountName="default" )
      api.accounts[ "work" ] = []
      task_cli.doProjectAdd( api, {}, Matcher.And(), [ "work:Q4Goals" ], {} )

      projects = api.getProjects()
      self.assertEqual( len( projects ), 1 )
      self.assertEqual( projects[ 0 ].accountName, "work" )
      self.assertEqual( projects[ 0 ].title, "Q4Goals" )
      self.assertTrue( projects[ 0 ].saved )

   def test_project_add_with_account_option( self ):
      api = MockCLIAccountManager( defaultAccountName="default" )
      api.accounts[ "personal" ] = []
      task_cli.doProjectAdd( api, { "account": "personal" }, Matcher.And(), [ "Fitness" ], {} )

      projects = api.getProjects()
      self.assertEqual( len( projects ), 1 )
      self.assertEqual( projects[ 0 ].accountName, "personal" )
      self.assertEqual( projects[ 0 ].title, "Fitness" )
      self.assertTrue( projects[ 0 ].saved )


if __name__ == '__main__':
   unittest.main()
