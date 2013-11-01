'''
Created on Jul 14, 2010

@author: duncantait
'''
from SimPy.Simulation import *
import pylab as pyl
import random
import math

class G():
    MEAN_TIME_BETWEEN_MESSAGES = 10
    Load_Monitor = []
    
class Load(Process):
    def __init__(self):
        Process.__init__(self)
        self.currentLoad = 0
    def execute(self):
        while True:
            self.currentLoad = abs(3*math.sin(now())) + random.paretovariate(3)
            yield hold,self,0.01
            G.Load_Monitor.append(self.currentLoad)

initialize()
L = Load()
activate(L,L.execute(),at=0.0)
simulate(until=10.0)

pyl.plot(G.Load_Monitor)
pyl.show()
