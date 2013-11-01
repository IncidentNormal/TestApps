import random
from SimPy.Simulation import *
from SimPy.Monitor import *
from SimPy.SimPlot import *
import pylab

group_sizes = { 'a': 20, 'b': 30, 'c': 10, 'd': 5, 'e': 12, 'f': 2 }
lamb_da = 2.0 #mean time between 'events' (maybe clicks of browser 'refresh' button)
personList = []
serverList = []

class Network(Process):
    def __init__(self):
        Process.__init__(self)
    def execute(self):
        while True: 
            for server in serverList:
                if server.theBuffer > 0:
                    yield get,self,server,1
            yield hold, self, 0.1

class Person(Process):
    def __init__(self, grp):
        Process.__init__(self)
        self.group = grp
    def execute(self):
        yield hold, self, random.expovariate(1.0/lamb_da)
        while True: 
            for server in serverList:
                if server.name==self.group:
                    
                    yield put,self,server,1
            yield hold, self, random.expovariate(1.0/lamb_da)

initialize()

for grp in group_sizes:
    server = Level(name=grp, unitName='bandWidth', capacity='unbounded', monitored=True)
    serverList.append(server)
    for person in range(group_sizes[grp]):
        p = Person(grp)
        activate(p,p.execute())
N = Network()
activate(N,N.execute())

simulate(until=30)

plt = SimPlot()
for s in serverList:
    plt.plotLine(s.bufferMon)
plt.mainloop()
print 'done'
        
        
