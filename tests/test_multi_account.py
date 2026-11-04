import os
import tempfile
import unittest
from pathlib import Path

from GoogleTasks import GoogleTasks, MultiAccountManager
import Matcher
import Project
import Task
from ShortId import updateShortIds


class TestAccountDiscovery( unittest.TestCase ):
   def test_discover_single_unsuffixed_default( self ):
      with tempfile.TemporaryDirectory() as tmpconfig, tempfile.TemporaryDirectory() as tmpcache:
         Path( tmpconfig, "app-credentials.json" ).write_text( "{}" )
         mam = MultiAccountManager.__new__( MultiAccountManager )
         mam.configDir = tmpconfig
         mam.cacheDir = tmpcache
         mam.activeAccount = None
         mam.accounts = {}
         mam.defaultAccountName = "default"
         mam._discoverAccounts()

         self.assertIn( "default", mam.discoveredAccounts )
         self.assertEqual( mam.defaultAccountName, "default" )
         self.assertEqual( mam.activeAccountNames, [ "default" ] )

   def test_discover_multiple_suffixed_accounts( self ):
      with tempfile.TemporaryDirectory() as tmpconfig, tempfile.TemporaryDirectory() as tmpcache:
         Path( tmpconfig, "app-credentials.json" ).write_text( "{}" )
         Path( tmpconfig, "app-credentials.json.work" ).write_text( "{}" )
         Path( tmpconfig, "app-credentials.json.personal" ).write_text( "{}" )
         mam = MultiAccountManager.__new__( MultiAccountManager )
         mam.configDir = tmpconfig
         mam.cacheDir = tmpcache
         mam.activeAccount = None
         mam.accounts = {}
         mam.defaultAccountName = "default"
         mam._discoverAccounts()

         self.assertCountEqual( mam.discoveredAccounts.keys(), [ "default", "work", "personal" ] )
         self.assertEqual( mam.defaultAccountName, "default" )
         self.assertCountEqual( mam.activeAccountNames, [ "default", "work", "personal" ] )

   def test_default_account_override_file( self ):
      with tempfile.TemporaryDirectory() as tmpconfig, tempfile.TemporaryDirectory() as tmpcache:
         Path( tmpconfig, "app-credentials.json" ).write_text( "{}" )
         Path( tmpconfig, "app-credentials.json.work" ).write_text( "{}" )
         Path( tmpconfig, "default-account" ).write_text( "work\n" )

         mam = MultiAccountManager.__new__( MultiAccountManager )
         mam.configDir = tmpconfig
         mam.cacheDir = tmpcache
         mam.activeAccount = None
         mam.accounts = {}
         mam.defaultAccountName = "default"
         mam._discoverAccounts()

         self.assertEqual( mam.defaultAccountName, "work" )

   def test_no_credentials_raises_error( self ):
      with tempfile.TemporaryDirectory() as tmpconfig, tempfile.TemporaryDirectory() as tmpcache:
         mam = MultiAccountManager.__new__( MultiAccountManager )
         mam.configDir = tmpconfig
         mam.cacheDir = tmpcache
         mam.activeAccount = None
         mam.accounts = {}
         mam.defaultAccountName = "default"

         with self.assertRaises( RuntimeError ) as ctx:
            mam._discoverAccounts()
         self.assertIn( "no credentials file", str( ctx.exception ) )

   def test_missing_default_account_raises_error( self ):
      with tempfile.TemporaryDirectory() as tmpconfig, tempfile.TemporaryDirectory() as tmpcache:
         Path( tmpconfig, "app-credentials.json.work" ).write_text( "{}" )
         Path( tmpconfig, "app-credentials.json.personal" ).write_text( "{}" )
         Path( tmpconfig, "default-account" ).write_text( "nonexistent\n" )

         mam = MultiAccountManager.__new__( MultiAccountManager )
         mam.configDir = tmpconfig
         mam.cacheDir = tmpcache
         mam.activeAccount = None
         mam.accounts = {}
         mam.defaultAccountName = "default"

         with self.assertRaises( RuntimeError ) as ctx:
            mam._discoverAccounts()
         self.assertIn( "Default account 'nonexistent' not found", str( ctx.exception ) )

   def test_single_account_override_via_active_account( self ):
      with tempfile.TemporaryDirectory() as tmpconfig, tempfile.TemporaryDirectory() as tmpcache:
         Path( tmpconfig, "app-credentials.json.work" ).write_text( "{}" )
         Path( tmpconfig, "app-credentials.json.personal" ).write_text( "{}" )
         Path( tmpconfig, "default-account" ).write_text( "personal\n" )

         mam = MultiAccountManager.__new__( MultiAccountManager )
         mam.configDir = tmpconfig
         mam.cacheDir = tmpcache
         mam.activeAccount = "work"
         mam.accounts = {}
         mam.defaultAccountName = "default"
         mam._discoverAccounts()

         self.assertEqual( mam.activeAccountNames, [ "work" ] )

   def test_invalid_active_account_raises_error( self ):
      with tempfile.TemporaryDirectory() as tmpconfig, tempfile.TemporaryDirectory() as tmpcache:
         Path( tmpconfig, "app-credentials.json" ).write_text( "{}" )

         mam = MultiAccountManager.__new__( MultiAccountManager )
         mam.configDir = tmpconfig
         mam.cacheDir = tmpcache
         mam.activeAccount = "unknown"
         mam.accounts = {}
         mam.defaultAccountName = "default"

         with self.assertRaises( RuntimeError ) as ctx:
            mam._discoverAccounts()
         self.assertIn( "Specified account 'unknown' not found", str( ctx.exception ) )

   def test_legacy_cache_migration( self ):
      with tempfile.TemporaryDirectory() as tmpconfig, tempfile.TemporaryDirectory() as tmpcache:
         # Create legacy cache files in root cacheDir
         proj_file = Path( tmpcache, "project-123.pickle" )
         task_file = Path( tmpcache, "tasks-123.pickle" )
         proj_file.write_text( "dummy-proj" )
         task_file.write_text( "dummy-task" )

         mam = MultiAccountManager.__new__( MultiAccountManager )
         mam.cacheDir = tmpcache
         mam._migrateLegacyCache()

         # Should be moved to <tmpcache>/default/
         default_dir = Path( tmpcache, "default" )
         self.assertTrue( ( default_dir / "project-123.pickle" ).exists() )
         self.assertTrue( ( default_dir / "tasks-123.pickle" ).exists() )
         self.assertFalse( proj_file.exists() )
         self.assertFalse( task_file.exists() )

   def test_partial_auth_failure_warns_and_continues( self ):
      from unittest.mock import patch
      with tempfile.TemporaryDirectory() as tmpconfig, tempfile.TemporaryDirectory() as tmpcache:
         Path( tmpconfig, "app-credentials.json" ).write_text( "{}" )
         Path( tmpconfig, "app-credentials.json.work" ).write_text( "{}" )

         mam = MultiAccountManager.__new__( MultiAccountManager )
         mam.configDir = tmpconfig
         mam.cacheDir = tmpcache
         mam.activeAccount = None
         mam.accounts = {}
         mam.defaultAccountName = "default"
         mam._discoverAccounts()

         def fake_auth( self_gt, alternateCredentials=None ):
            if self_gt.accountName == "work":
               raise RuntimeError( "Auth expired for work" )

         with patch.object( GoogleTasks, "authenticate", fake_auth ):
            import io
            import sys
            old_err = sys.stderr
            sys.stderr = io.StringIO()
            try:
               mam._authenticateAll()
               err = sys.stderr.getvalue()
            finally:
               sys.stderr = old_err

            self.assertIn( "Warning: failed to authenticate account 'work'", err )
            self.assertIn( "default", mam.accounts )
            self.assertNotIn( "work", mam.accounts )

   def test_all_auth_failure_raises( self ):
      from unittest.mock import patch
      with tempfile.TemporaryDirectory() as tmpconfig, tempfile.TemporaryDirectory() as tmpcache:
         Path( tmpconfig, "app-credentials.json" ).write_text( "{}" )

         mam = MultiAccountManager.__new__( MultiAccountManager )
         mam.configDir = tmpconfig
         mam.cacheDir = tmpcache
         mam.activeAccount = None
         mam.accounts = {}
         mam.defaultAccountName = "default"
         mam._discoverAccounts()

         def fake_auth( self_gt, alternateCredentials=None ):
            raise RuntimeError( "Network error" )

         with patch.object( GoogleTasks, "authenticate", fake_auth ):
            import io
            import sys
            old_err = sys.stderr
            sys.stderr = io.StringIO()
            try:
               with self.assertRaises( RuntimeError ):
                  mam._authenticateAll()
            finally:
               sys.stderr = old_err


class DummyProject( Project.Project ):
   def __init__( self, title, accountName="default", apiId=None ):
      super().__init__( title, accountName=accountName )
      self.apiId = apiId or f"proj-{accountName}-{title}"
      self.apiObject = { "id": self.apiId, "title": title }


class DummyTask( Task.Task ):
   def __init__( self, project, title, apiId=None, dueDate=None ):
      super().__init__( project )
      self.title = title
      self.apiId = apiId or f"task-{project.accountName}-{title}"
      self.apiObject = { "id": self.apiId, "title": title, "position": "0" }
      self.dueDate = dueDate

   def apiOrderKey( self ):
      return 0


class DummyTaskApi:
   def __init__( self, accountName, projects ):
      self.accountName = accountName
      self._projects = projects
      self.manager = None

   def getProjects( self, updateIds=True ):
      return list( self._projects )


class TestShortIdUniquenessAndLength( unittest.TestCase ):
   def test_global_short_ids_across_three_accounts( self ):
      mam = MultiAccountManager.__new__( MultiAccountManager )
      mam.defaultAccountName = "default"
      mam.allTasks = set()
      mam.allProjects = []

      # Create projects and tasks for 3 accounts: default, work, personal
      p_default = DummyProject( "Inbox", accountName="default", apiId="gtasks_def_inbox_12345" )
      p_work = DummyProject( "WorkInbox", accountName="work", apiId="gtasks_work_inbox_67890" )
      p_personal = DummyProject( "Chores", accountName="personal", apiId="gtasks_pers_chores_abcde" )

      t1 = DummyTask( p_default, "Task 1", apiId="gt_def_t1_001" )
      t2 = DummyTask( p_work, "Task 2", apiId="gt_work_t2_002" )
      t3 = DummyTask( p_personal, "Task 3", apiId="gt_pers_t3_003" )
      t4 = DummyTask( p_work, "Task 4", apiId="gt_work_t4_004" )

      mam.accounts = {
         "default": DummyTaskApi( "default", [ p_default ] ),
         "work": DummyTaskApi( "work", [ p_work ] ),
         "personal": DummyTaskApi( "personal", [ p_personal ] ),
      }

      projects = mam.getProjects()
      self.assertEqual( len( projects ), 3 )

      # Check project short IDs: all start with p, unique, equal length
      proj_ids = [ p.shortId for p in projects ]
      self.assertEqual( len( proj_ids ), len( set( proj_ids ) ) )
      self.assertTrue( all( pid.startswith( "p" ) for pid in proj_ids ) )
      proj_lens = { len( pid ) for pid in proj_ids }
      self.assertEqual( len( proj_lens ), 1, "All project shortIds must have identical fixed length" )

      # Check task short IDs
      mam.assignTaskIds( [ t1, t2, t3, t4 ] )
      task_ids = [ t.shortId for t in [ t1, t2, t3, t4 ] ]
      self.assertEqual( len( task_ids ), 4 )
      self.assertEqual( len( task_ids ), len( set( task_ids ) ) )
      self.assertTrue( all( tid.startswith( "t" ) for tid in task_ids ) )
      task_lens = { len( tid ) for tid in task_ids }
      self.assertEqual( len( task_lens ), 1, "All task shortIds must have identical fixed length" )

   def test_new_project_account_delegation( self ):
      mam = MultiAccountManager.__new__( MultiAccountManager )
      mam.defaultAccountName = "personal"
      mam.accounts = {
         "work": DummyTaskApi( "work", [] ),
         "personal": DummyTaskApi( "personal", [] ),
      }

      # Add newProject to DummyTaskApi for this test
      for name, api in mam.accounts.items():
         api.newProject = lambda n=name: DummyProject( "", accountName=n )

      p1 = mam.newProject()
      self.assertEqual( p1.accountName, "personal" )

      p2 = mam.newProject( accountName="work" )
      self.assertEqual( p2.accountName, "work" )

      with self.assertRaises( RuntimeError ) as ctx:
         mam.newProject( accountName="nonexistent" )
      self.assertIn( "Account 'nonexistent' not found", str( ctx.exception ) )


class TestQueryMatchingAST( unittest.TestCase ):
   def setUp( self ):
      self.p_work = DummyProject( "Inbox", accountName="work" )
      self.p_pers = DummyProject( "Inbox", accountName="personal" )
      self.t_work = DummyTask( self.p_work, "Review budget @urgent", dueDate="2026-11-04" )
      self.t_pers = DummyTask( self.p_pers, "Buy groceries @urgent", dueDate="2026-11-05" )

   def test_account_matcher_direct( self ):
      m_work = Matcher.AccountMatcher( "work" )
      m_pers = Matcher.AccountMatcher( "personal" )

      self.assertTrue( m_work.match( self.p_work ) )
      self.assertFalse( m_work.match( self.p_pers ) )
      self.assertTrue( m_work.match( self.t_work ) )
      self.assertFalse( m_work.match( self.t_pers ) )

      self.assertFalse( m_pers.match( self.p_work ) )
      self.assertTrue( m_pers.match( self.p_pers ) )
      self.assertFalse( m_pers.match( self.t_work ) )
      self.assertTrue( m_pers.match( self.t_pers ) )

   def test_account_matcher_case_insensitive( self ):
      m_work = Matcher.AccountMatcher( "WORK" )
      self.assertTrue( m_work.match( self.p_work ) )
      self.assertTrue( m_work.match( self.t_work ) )

   def test_project_word_matcher_composite( self ):
      # p:work:Inbox should only match work:Inbox
      m_comp = Project.WordMatcher( "work:Inbox" )
      self.assertTrue( m_comp.match( self.p_work ) )
      self.assertFalse( m_comp.match( self.p_pers ) )
      self.assertTrue( m_comp.match( self.t_work ) )
      self.assertFalse( m_comp.match( self.t_pers ) )

      # p:Inbox should match both
      m_inbox = Project.WordMatcher( "Inbox" )
      self.assertTrue( m_inbox.match( self.p_work ) )
      self.assertTrue( m_inbox.match( self.p_pers ) )

   def test_boolean_composite_queries( self ):
      # a:work due:2026-11-04 OR a:personal @urgent
      and1 = Matcher.And()
      and1.add( Matcher.AccountMatcher( "work" ) )
      and1.add( Task.DueMatcher( "2026-11-04" ) )

      and2 = Matcher.And()
      and2.add( Matcher.AccountMatcher( "personal" ) )
      and2.add( Task.WordMatcher( "@urgent" ) )

      root = Matcher.Or()
      root.add( and1 )
      root.add( and2 )

      self.assertTrue( root.match( self.t_work ) )
      self.assertTrue( root.match( self.t_pers ) )

      # Negative check: non-matching due date in work
      t_work2 = DummyTask( self.p_work, "Other work", dueDate="2026-12-01" )
      self.assertFalse( root.match( t_work2 ) )


class TestProjectParsingAndSorting( unittest.TestCase ):
   def test_project_parse_with_account( self ):
      p = Project.Project.parse( "* (p01) work:Inbox" )
      self.assertIsNotNone( p )
      self.assertEqual( p.shortId, "p01" )
      self.assertEqual( p.accountName, "work" )
      self.assertEqual( p.title, "Inbox" )
      self.assertEqual( p.displayName, "work:Inbox" )
      self.assertEqual( str( p ), "* (p01) work:Inbox" )

   def test_project_parse_new_with_account( self ):
      p = Project.Project.parse( "* (p) personal:Chores" )
      self.assertIsNotNone( p )
      self.assertEqual( p.shortId, "p" )
      self.assertEqual( p.accountName, "personal" )
      self.assertEqual( p.title, "Chores" )
      self.assertEqual( p.displayName, "personal:Chores" )

   def test_project_parse_legacy_line_falls_back_to_default_account( self ):
      p = Project.Project.parse( "* (p01) Inbox", defaultAccount="default" )
      self.assertIsNotNone( p )
      self.assertEqual( p.shortId, "p01" )
      self.assertEqual( p.accountName, "default" )
      self.assertEqual( p.title, "Inbox" )
      self.assertEqual( p.displayName, "default:Inbox" )

   def test_project_sort_default_first_then_alphabetical_and_gtd( self ):
      p_def_inbox = DummyProject( "Inbox", accountName="default" )
      p_def_sched = DummyProject( "Scheduled", accountName="default" )
      p_def_alpha = DummyProject( "Admin", accountName="default" )

      p_work_sched = DummyProject( "Scheduled", accountName="work" )
      p_work_inbox = DummyProject( "Inbox", accountName="work" )
      p_work_alpha = DummyProject( "Projects", accountName="work" )

      p_pers_inbox = DummyProject( "Inbox", accountName="personal" )
      p_pers_alpha = DummyProject( "Chores", accountName="personal" )

      all_projects = [
         p_work_alpha, p_pers_alpha, p_def_alpha,
         p_work_inbox, p_pers_inbox, p_def_inbox,
         p_work_sched, p_def_sched
      ]

      sorted_projects = Project.Project.sort( all_projects, defaultAccount="default" )
      expected_order = [
         p_def_sched,
         p_def_inbox,
         p_def_alpha,
         p_pers_inbox,
         p_pers_alpha,
         p_work_sched,
         p_work_inbox,
         p_work_alpha,
      ]

      self.assertEqual( sorted_projects, expected_order )


if __name__ == '__main__':
   unittest.main()
