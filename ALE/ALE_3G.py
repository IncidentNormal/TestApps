'''
Created on Nov 23, 2010

@author: duncantait

FLSU Simple modelling simulation - based on connection only. xDL HDL/LDL will simply be a parameterised time chunk after successful connection 
'''
from SimPy.Simulation import *

class G():
    num_frequencies = 10
    dwell_time = 1.35
    
    
class Network():
    frequencies = [Store(name='chan'+str(i)) for i in range(G.num_frequencies)]
    
class Scanning(Process):
    def __init__(self, ID):
        Process.__init__(self)
        self.ID = ID
    def execute(self):
            