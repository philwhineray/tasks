import unittest
from ShortId import Trie, updateShortIds


class DummyItem:
   def __init__( self, itemId ):
      self.apiObject = { "id": itemId } if itemId is not None else {}
      self.shortId = None


class TestShortIdResilience( unittest.TestCase ):
   def test_duplicate_items_do_not_explode_fixed_length( self ):
      # 2 distinct items, each duplicated 3 times
      items = [
         DummyItem( "task_alpha" ),
         DummyItem( "task_beta" ),
         DummyItem( "task_alpha" ),
         DummyItem( "task_beta" ),
         DummyItem( "task_alpha" ),
         DummyItem( "task_beta" ),
      ]
      updateShortIds( items, "t" )

      # Short ID length must be compact (prefix length 1 hex char + 't' = 2 chars), NOT 65
      self.assertEqual( len( items[ 0 ].shortId ), 2 )
      self.assertEqual( items[ 0 ].shortId, items[ 2 ].shortId )
      self.assertEqual( items[ 1 ].shortId, items[ 3 ].shortId )
      self.assertNotEqual( items[ 0 ].shortId, items[ 1 ].shortId )

   def test_missing_or_empty_api_id_handled_gracefully( self ):
      items = [
         DummyItem( "task_valid" ),
         DummyItem( None ),
         DummyItem( "" ),
      ]
      # Should not raise KeyError or AttributeError
      updateShortIds( items, "t" )
      self.assertIsNotNone( items[ 0 ].shortId )
      self.assertIsNone( items[ 1 ].shortId )
      self.assertIsNone( items[ 2 ].shortId )


if __name__ == '__main__':
   unittest.main()
