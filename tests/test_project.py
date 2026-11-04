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


if __name__ == '__main__':
   unittest.main()
