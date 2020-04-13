#!/usr/bin/env python3

class Project:
   def __init__( self, title ):
      self.shortId = None
      self.apiRef = None
      self.apiObject = None
      self.title = title

   def __str__( self ):
      return self.title
