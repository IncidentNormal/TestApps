import random
from SimPy.Simulation import *
from SimPy.Monitor import *
from SimPy.SimPlot import *
import pylab

TestList = []

class Test(Process):
    def __init__(self,i):
        Process.__init__(self)
        self.ID = i
        self.test_s = Store(name='s_store')
    def go(self):
        while True:
            for T in TestList:
                strIn = 'test' + str(self.ID)
                yield put, self, T.test_s, [strIn]
                yield hold, self, 1

initialize()
for i in range(10):
    T = Test(i)
    activate(T, T.go(), at=0.0)
    TestList.append(T)
simulate(until=10)

for T in TestList:
    print T.test_s.theBuffer

        
        
        
