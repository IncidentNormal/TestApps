'''
Created on Oct 29, 2010

@author: duncantait
'''
from SimPy.SimulationTrace import *
import MHS,ALE,Env

initialize()
simulate(until=1000)
print 'done'