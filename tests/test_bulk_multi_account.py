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

   def test_unknown_task_id_raises_parse_error( self ):
      mam = MockBulkAccountManager()
      p_work = MockBulkProject( "Inbox", accountName="work", shortId="p01" )
      mam.addProject( p_work )

      edited_buffer = (
         "* (p01) work:Inbox\n"
         "** (t99) [ ] Mistyped task id\n"
      )

      with self.assertRaises( Project.ParseError ) as ctx:
         Project.read( mam, {}, io.StringIO( edited_buffer ) )
      self.assertIn( "unknown task id: t99", str( ctx.exception ) )

   def test_unknown_project_id_raises_parse_error( self ):
      mam = MockBulkAccountManager()
      p_work = MockBulkProject( "Inbox", accountName="work", shortId="p01" )
      mam.addProject( p_work )

      edited_buffer = (
         "* (p99) work:Nonexistent Project\n"
         "** (t) [ ] New task\n"
      )

      with self.assertRaises( Project.ParseError ) as ctx:
         Project.read( mam, {}, io.StringIO( edited_buffer ) )
      self.assertIn( "unknown project id: p99", str( ctx.exception ) )


class FakeAdapterProject( Project.Project ):
   def __init__( self, taskApi, title, tasks_info ):
      super().__init__( title, accountName=taskApi.accountName )
      self.taskApi = taskApi
      self.apiObject = { "id": f"{taskApi.accountName}_{title}", "title": title }
      self.apiId = self.apiObject[ "id" ]
      self.tasks_info = tasks_info
      self.loaded = False

   def save( self ):
      pass

   def delete( self ):
      pass

   def get_tasks( self ):
      if not self.loaded:
         self.loaded = True
         for t_id, t_title in self.tasks_info:
            FakeAdapterTask( self, { "id": t_id, "title": t_title } )
         self.taskApi.assignTaskIds( self._tasks )
      return super().get_tasks()

   tasks = property( get_tasks )

   def newTask( self ):
      t = FakeAdapterTask( self, { "id": None, "title": "" } )
      return t


class FakeAdapterTask( Task.Task ):
   def __init__( self, project, apiObject ):
      super().__init__( project )
      self.taskApi = project.taskApi
      self.apiObject = apiObject
      self.apiId = apiObject.get( "id" )
      self.title = apiObject.get( "title" )
      self.is_saved = False
      self.is_deleted = False

   def save( self ):
      self.is_saved = True
      self.taskApi.saved_tasks.append( self )

   def delete( self ):
      self.is_deleted = True
      self.taskApi.deleted_tasks.append( self )


class FakeGoogleTasksAdapter:
   def __init__( self, name, tasks_data ):
      self.accountName = name
      self.projects = []
      self.allTasks = set()
      self.manager = None
      self.tasks_data = tasks_data
      self.saved_tasks = []
      self.deleted_tasks = []

   def getProjects( self, updateIds=True ):
      self.projects = []
      self.allTasks = set()
      for p_title, tasks in self.tasks_data.items():
         p = FakeAdapterProject( self, p_title, tasks )
         self.projects.append( p )
      if updateIds:
         from ShortId import updateShortIds
         updateShortIds( self.projects, "p" )
      return self.projects

   def assignTaskIds( self, newTasks ):
      if self.manager is not None:
         self.manager.assignTaskIds( newTasks )
      else:
         self.allTasks |= set( newTasks )
         from ShortId import updateShortIds
         updateShortIds( self.allTasks, "t" )


class TestBulkRoundTripRegression( unittest.TestCase ):
   def test_round_trip_bulk_edit_does_not_duplicate_tasks( self ):
      from GoogleTasks import MultiAccountManager

      mam = MultiAccountManager.__new__( MultiAccountManager )
      mam.defaultAccountName = "work"
      mam.allProjects = []
      mam.allTasks = set()

      gt_work = FakeGoogleTasksAdapter( "work", { "Inbox": [ ( "task_w1", "Work Task 1" ) ] } )
      gt_work.manager = mam
      gt_pers = FakeGoogleTasksAdapter( "personal", { "Inbox": [ ( "task_p1", "Personal Task 1" ) ] } )
      gt_pers.manager = mam
      mam.accounts = { "work": gt_work, "personal": gt_pers }

      # First pass: Project.write
      projects = mam.getProjects()
      buf = io.StringIO()
      Project.write( projects, {}, Matcher.And(), outfile=buf )
      written_text = buf.getvalue()

      self.assertIn( "work:Inbox", written_text )
      self.assertIn( "personal:Inbox", written_text )

      # Second pass: Project.read without changes
      read_buf = io.StringIO( written_text )
      Project.read( mam, {}, infile=read_buf )

      # Assert NO duplicate tasks were created
      new_work_tasks = [ t for t in gt_work.saved_tasks if t.apiId is None ]
      new_pers_tasks = [ t for t in gt_pers.saved_tasks if t.apiId is None ]

      self.assertEqual( len( new_work_tasks ), 0, "No duplicate tasks should be created in work account" )
      self.assertEqual( len( new_pers_tasks ), 0, "No duplicate tasks should be created in personal account" )

   def test_multi_account_manager_resets_all_tasks_on_get_projects( self ):
      from GoogleTasks import MultiAccountManager

      mam = MultiAccountManager.__new__( MultiAccountManager )
      mam.defaultAccountName = "default"
      mam.accounts = {}
      mam.allProjects = []
      mam.allTasks = { "dummy_task" }

      mam.getProjects()
      self.assertEqual( len( mam.allTasks ), 0, "allTasks must be cleared on getProjects()" )


if __name__ == '__main__':
   unittest.main()
