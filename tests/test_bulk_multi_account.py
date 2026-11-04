import io
import unittest

import Matcher
import Project
import Task


class MockBulkTask( Task.Task ):
   def __init__( self, project ):
      super().__init__( project )
      self.saved = False
      self.deleted = False
      self.apiId = None

   def apiOrderKey( self ):
      return 0

   def save( self ):
      self.saved = True

   def delete( self ):
      self.deleted = True


class MockBulkProject( Project.Project ):
   def __init__( self, title, accountName="default", shortId=None ):
      super().__init__( title, accountName=accountName )
      self.shortId = shortId
      self.saved = False
      self.deleted = False
      self.createdTasks = []

   def save( self ):
      self.saved = True

   def delete( self ):
      self.deleted = True

   def newTask( self ):
      t = MockBulkTask( self )
      self.createdTasks.append( t )
      return t


class MockBulkAccountManager:
   def __init__( self, defaultAccountName="default" ):
      self.defaultAccountName = defaultAccountName
      self.accounts = {}
      self._projects = []

   def addProject( self, project ):
      self._projects.append( project )
      if project.accountName not in self.accounts:
         self.accounts[ project.accountName ] = []
      self.accounts[ project.accountName ].append( project )

   def getProjects( self ):
      return list( self._projects )

   def newProject( self, accountName=None ):
      if accountName is None:
         accountName = self.defaultAccountName
      p = MockBulkProject( "", accountName=accountName )
      self.addProject( p )
      return p


class TestBulkMultiAccount( unittest.TestCase ):
   def test_in_buffer_representation( self ):
      mam = MockBulkAccountManager()
      p_work = MockBulkProject( "Inbox", accountName="work", shortId="p01" )
      p_pers = MockBulkProject( "Inbox", accountName="personal", shortId="p02" )
      mam.addProject( p_work )
      mam.addProject( p_pers )

      t1 = MockBulkTask( p_work )
      t1.shortId = "t01"
      t1.title = "Submit Q4 report"

      t2 = MockBulkTask( p_pers )
      t2.shortId = "t02"
      t2.title = "Buy milk"

      buf = io.StringIO()
      Project.write( mam.getProjects(), {}, Matcher.And(), outfile=buf )
      output = buf.getvalue()

      self.assertIn( "* (p01) work:Inbox", output )
      self.assertIn( "** (t01) [ ] Submit Q4 report", output )
      self.assertIn( "* (p02) personal:Inbox", output )
      self.assertIn( "** (t02) [ ] Buy milk", output )

   def test_cross_account_task_move( self ):
      mam = MockBulkAccountManager()
      p_work = MockBulkProject( "Inbox", accountName="work", shortId="p01" )
      p_pers = MockBulkProject( "Inbox", accountName="personal", shortId="p02" )
      mam.addProject( p_work )
      mam.addProject( p_pers )

      t1 = MockBulkTask( p_work )
      t1.shortId = "t01"
      t1.title = "Call plumber"
      t1.notes = "Get quote for kitchen sink"
      t1.dueDate = "2026-11-10"

      # Simulate editing buffer: t01 moved under personal:Inbox
      edited_buffer = (
         "* (p01) work:Inbox\n"
         "* (p02) personal:Inbox\n"
         "** (t01) [ ] [2026-11-10] Call plumber\n"
         "Get quote for kitchen sink\n"
      )

      Project.read( mam, { "verbose": True }, io.StringIO( edited_buffer ) )

      # Assert original task in work was deleted
      self.assertTrue( t1.deleted )

      # Assert new task in personal was created and saved with identical metadata
      saved_personal_tasks = [ t for t in p_pers.tasks if t.saved ]
      self.assertEqual( len( saved_personal_tasks ), 1 )
      new_task = saved_personal_tasks[ 0 ]
      self.assertEqual( new_task.title, "Call plumber" )
      self.assertEqual( new_task.notes, "Get quote for kitchen sink" )
      self.assertEqual( new_task.dueDate, "2026-11-10" )
      self.assertEqual( new_task.accountName, "personal" )
      self.assertIs( new_task.project, p_pers )

   def test_subtask_hierarchy_preservation_across_accounts( self ):
      mam = MockBulkAccountManager()
      p_work = MockBulkProject( "Inbox", accountName="work", shortId="p01" )
      p_pers = MockBulkProject( "Inbox", accountName="personal", shortId="p02" )
      mam.addProject( p_work )
      mam.addProject( p_pers )

      parent_task = MockBulkTask( p_work )
      parent_task.shortId = "t10"
      parent_task.title = "Family Vacation"

      child1 = MockBulkTask( p_work )
      child1.shortId = "t11"
      child1.title = "Book flights"
      child1.parentTask = parent_task

      child2 = MockBulkTask( p_work )
      child2.shortId = "t12"
      child2.title = "Reserve hotel"
      child2.parentTask = parent_task

      # In outliner buffer, all 3 tasks are moved under personal:Inbox
      edited_buffer = (
         "* (p01) work:Inbox\n"
         "* (p02) personal:Inbox\n"
         "** (t10) [ ] Family Vacation\n"
         "*** (t11) [ ] Book flights\n"
         "*** (t12) [ ] Reserve hotel\n"
      )

      Project.read( mam, {}, io.StringIO( edited_buffer ) )

      # Assert source tasks are deleted
      self.assertTrue( parent_task.deleted )
      self.assertTrue( child1.deleted )
      self.assertTrue( child2.deleted )

      # Assert target tasks created in personal:Inbox with hierarchy preserved
      personal_tasks = [ t for t in p_pers.tasks if t.saved ]
      self.assertEqual( len( personal_tasks ), 3 )

      # Find target parent
      target_parent = next( t for t in personal_tasks if t.title == "Family Vacation" )
      self.assertIsNone( target_parent.parentTask )
      self.assertEqual( target_parent.level(), 0 )

      target_c1 = next( t for t in personal_tasks if t.title == "Book flights" )
      target_c2 = next( t for t in personal_tasks if t.title == "Reserve hotel" )

      self.assertIs( target_c1.parentTask, target_parent )
      self.assertIs( target_c2.parentTask, target_parent )
      self.assertEqual( target_c1.level(), 1 )
      self.assertEqual( target_c2.level(), 1 )

   def test_changing_project_account_raises_parse_error( self ):
      mam = MockBulkAccountManager()
      p_work = MockBulkProject( "Inbox", accountName="work", shortId="p01" )
      mam.addProject( p_work )

      # Try changing p01 account from work to personal
      edited_buffer = (
         "* (p01) personal:Inbox\n"
      )

      with self.assertRaises( Project.ParseError ) as ctx:
         Project.read( mam, {}, io.StringIO( edited_buffer ) )
      self.assertIn( "changing project account from 'work' to 'personal' is not supported", str( ctx.exception ) )

   def test_duplicate_project_name_in_same_account_raises_parse_error( self ):
      mam = MockBulkAccountManager()
      p_work = MockBulkProject( "Inbox", accountName="work", shortId="p01" )
      mam.addProject( p_work )

      # Try creating a new project with the same name in work
      edited_buffer = (
         "* (p01) work:Inbox\n"
         "* (p) work:Inbox\n"
      )

      with self.assertRaises( Project.ParseError ) as ctx:
         Project.read( mam, {}, io.StringIO( edited_buffer ) )
      self.assertIn( "already exists, refusing to duplicate name", str( ctx.exception ) )

   def test_same_project_name_in_different_accounts_is_permitted( self ):
      mam = MockBulkAccountManager()
      p_work = MockBulkProject( "Inbox", accountName="work", shortId="p01" )
      mam.addProject( p_work )

      # Creating Inbox in personal account when work already has Inbox
      edited_buffer = (
         "* (p01) work:Inbox\n"
         "* (p) personal:Inbox\n"
      )

      # Should succeed without error
      Project.read( mam, {}, io.StringIO( edited_buffer ) )

      pers_projects = [ p for p in mam.getProjects() if p.accountName == "personal" ]
      self.assertEqual( len( pers_projects ), 1 )
      self.assertEqual( pers_projects[ 0 ].title, "Inbox" )
      self.assertTrue( pers_projects[ 0 ].saved )

   def test_unparsed_children_migrated_recursively( self ):
      mam = MockBulkAccountManager()
      p_work = MockBulkProject( "Inbox", accountName="work", shortId="p01" )
      p_pers = MockBulkProject( "Inbox", accountName="personal", shortId="p02" )
      mam.addProject( p_work )
      mam.addProject( p_pers )

      parent_task = MockBulkTask( p_work )
      parent_task.shortId = "t10"
      parent_task.title = "Parent Project Task"

      child1 = MockBulkTask( p_work )
      child1.shortId = "t11"
      child1.title = "Hidden Child Task"
      child1.parentTask = parent_task

      # Only parent_task is in the buffer (child1 was omitted from buffer)
      edited_buffer = (
         "* (p01) work:Inbox\n"
         "* (p02) personal:Inbox\n"
         "** (t10) [ ] Parent Project Task\n"
      )

      Project.read( mam, {}, io.StringIO( edited_buffer ) )

      # Parent and child should both be deleted from work
      self.assertTrue( parent_task.deleted )
      self.assertTrue( child1.deleted )

      # In personal, parent and child should both be created and saved
      personal_tasks = [ t for t in p_pers.tasks if t.saved ]
      self.assertEqual( len( personal_tasks ), 2 )

      target_parent = next( t for t in personal_tasks if t.title == "Parent Project Task" )
      target_child = next( t for t in personal_tasks if t.title == "Hidden Child Task" )
      self.assertIs( target_child.parentTask, target_parent )

   def test_source_deletion_failure_warns_and_raises( self ):
      import sys
      mam = MockBulkAccountManager()
      p_work = MockBulkProject( "Inbox", accountName="work", shortId="p01" )
      p_pers = MockBulkProject( "Inbox", accountName="personal", shortId="p02" )
      mam.addProject( p_work )
      mam.addProject( p_pers )

      t1 = MockBulkTask( p_work )
      t1.shortId = "t01"
      t1.title = "Failing Task"

      def fail_delete():
         raise RuntimeError( "API deletion failed" )

      t1.delete = fail_delete

      edited_buffer = (
         "* (p01) work:Inbox\n"
         "* (p02) personal:Inbox\n"
         "** (t01) [ ] Failing Task\n"
      )

      old_err = sys.stderr
      sys.stderr = io.StringIO()
      try:
         with self.assertRaises( RuntimeError ):
            Project.read( mam, {}, io.StringIO( edited_buffer ) )
         err = sys.stderr.getvalue()
      finally:
         sys.stderr = old_err

      self.assertIn( "Warning: failed to delete source task t01", err )


if __name__ == '__main__':
   unittest.main()
