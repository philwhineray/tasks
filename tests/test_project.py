import unittest
import Project
import Task


class TestProjectRemoveTask( unittest.TestCase ):
   def test_remove_task_directly( self ):
      project = Project.Project( "Work" )
      task = Task.Task( project )
      self.assertIn( task, project.tasks )
      self.assertEqual( len( project.tasks ), 1 )

      project.removeTask( task )
      self.assertNotIn( task, project.tasks )
      self.assertEqual( len( project.tasks ), 0 )

   def test_remove_task_not_in_project_raises_key_error( self ):
      p1 = Project.Project( "Work" )
      p2 = Project.Project( "Personal" )
      task = Task.Task( p1 )

      with self.assertRaises( KeyError ):
         p2.removeTask( task )

   def test_task_project_reassignment_removes_from_old_project( self ):
      p1 = Project.Project( "Work" )
      p2 = Project.Project( "Personal" )
      task = Task.Task( p1 )
      task.title = "Important task"

      self.assertIn( task, p1.tasks )
      self.assertNotIn( task, p2.tasks )
      self.assertEqual( len( p1.tasks ), 1 )
      self.assertEqual( len( p2.tasks ), 0 )

      task.project = p2

      self.assertNotIn( task, p1.tasks )
      self.assertIn( task, p2.tasks )
      self.assertEqual( len( p1.tasks ), 0 )
      self.assertEqual( len( p2.tasks ), 1 )
      self.assertEqual( task.project, p2 )


class MockTask( Task.Task ):
   def __init__( self, project ):
      super().__init__( project )
      self.saved = False
      self.deleted = False
      self.apiId = None

   def save( self ):
      self.saved = True

   def delete( self ):
      self.deleted = True


class MockProject( Project.Project ):
   def __init__( self, title, shortId=None ):
      super().__init__( title )
      self.shortId = shortId
      self.saved = False
      self.deleted = False

   def save( self ):
      self.saved = True

   def delete( self ):
      self.deleted = True

   def newTask( self ):
      return MockTask( self )


class MockTaskApi:
   def __init__( self, projects=None ):
      self._projects = list( projects ) if projects else []

   def getProjects( self ):
      return self._projects

   def newProject( self ):
      p = MockProject( "" )
      self._projects.append( p )
      return p


class TestProjectRead( unittest.TestCase ):
   def test_read_creates_new_task_under_current_project( self ):
      p1 = MockProject( "Project1", "p01" )
      p2 = MockProject( "Project2", "p02" )
      api = MockTaskApi( [ p1, p2 ] )

      data = (
         "* (p01) Project1\n"
         "** (t) [ ] Task for Project 1\n"
         "* (p02) Project2\n"
         "** (t) [ ] Task for Project 2\n"
      )

      import io
      Project.read( api, {}, io.StringIO( data ) )

      saved_p1 = [ t for t in p1.tasks if getattr( t, "saved", False ) ]
      saved_p2 = [ t for t in p2.tasks if getattr( t, "saved", False ) ]

      self.assertEqual( len( saved_p1 ), 1 )
      self.assertEqual( len( saved_p2 ), 1 )
      self.assertEqual( saved_p1[ 0 ].title, "Task for Project 1" )
      self.assertIs( saved_p1[ 0 ].project, p1 )
      self.assertEqual( saved_p2[ 0 ].title, "Task for Project 2" )
      self.assertIs( saved_p2[ 0 ].project, p2 )

   def test_read_creates_new_task_in_brand_new_project( self ):
      api = MockTaskApi()

      data = (
         "* (p) Brand New Project\n"
         "** (t) [ ] Task in New Project\n"
      )

      import io
      Project.read( api, {}, io.StringIO( data ) )

      self.assertEqual( len( api._projects ), 1 )
      new_proj = api._projects[ 0 ]
      self.assertEqual( new_proj.title, "Brand New Project" )
      saved_tasks = [ t for t in new_proj.tasks if getattr( t, "saved", False ) ]
      self.assertEqual( len( saved_tasks ), 1 )
      self.assertEqual( saved_tasks[ 0 ].title, "Task in New Project" )
      self.assertIs( saved_tasks[ 0 ].project, new_proj )


if __name__ == '__main__':
   unittest.main()
