#!/usr/bin/env python3

from hashlib import sha256

class Trie:
    def __init__( self ):
        self.letters = {}

    def addString( self , s ):
        letters = self.letters
        for c in s:
            if c not in letters:
                letters[ c ] = { "freq" : 1 }
            else:
                letters[ c ][ "freq" ] += 1
            letters = letters[ c ]
        letters[ "*" ] = True #marks the end of word
        
    def generateUniquePrefix( self, s ):
        prefix = []
        letters = self.letters
        for c in s:
            prefix.append( c )
            if letters[ c ][ "freq" ] == 1:
                break
            letters = letters[ c ]
            
        return "".join( prefix )

def updateShortIds( tasks, extraPrefix="" ):
   trie = Trie()
   idToHash = {}

   for task in tasks:
      taskId = task.apiObject[ 'id' ]
      idToHash[ taskId ] = sha256( taskId.encode( 'utf8' ) ).hexdigest()
      trie.addString( idToHash[ taskId ] )

   fixedLen = 0
   for task in tasks:
      taskId = task.apiObject[ 'id' ]
      prefix = trie.generateUniquePrefix( idToHash[ taskId ] )
      prefixLen = len( prefix )
      if prefixLen > fixedLen:
         fixedLen = prefixLen

   for task in tasks:
      taskId = task.apiObject[ 'id' ]
      task.shortId = extraPrefix + idToHash[ taskId ][ : fixedLen ]
