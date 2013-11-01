from SimPy.Simulation import *
import pylab as pyl
import numpy as np
import random
import math


class G():
    MEAN_TIME_BETWEEN_REQUEST = 2.
    MEAN_TIME_HOLD_CHANNEL = 1.
    MEAN_BACKOFF = 0.1
    NUM_DEVICE = 30
    NUM_CHAN = 1
    MAX_TIME = 1000

    endSeries = np.zeros(100)
    ySeries = np.zeros(100)
    Count = 0

class Cont():
    CSMA = Resource(capacity=G.NUM_CHAN)
    Channel = Resource(capacity=G.NUM_CHAN)
    DeviceList = []

class Device(Process):
    def __init__(self,ID):
        Process.__init__(self)
        self.ID = ID
    def execute(self):
        yield hold,self,random.expovariate(1/G.MEAN_TIME_BETWEEN_REQUEST)
        while True:
            if (not len(Cont.CSMA.activeQ)==G.NUM_CHAN) and (not (Cont.Channel.activeQ)==G.NUM_CHAN):
                yield request,self,Cont.CSMA
                yield hold,self,0.01
                if self.interrupted():
                    yield release,self,Cont.CSMA
                    #print self.ID, 'was interrupted! -- Collision occured'
                    #G.Count += 1
                    yield hold,self,random.expovariate(1/G.MEAN_BACKOFF)
                else:
                    G.Count += 1
                    yield release,self,Cont.CSMA
                    yield request,self,Cont.Channel
                    yield hold,self,random.expovariate(1/G.MEAN_TIME_HOLD_CHANNEL)
                    yield release,self,Cont.Channel
                    yield hold,self,random.expovariate(1/G.MEAN_TIME_BETWEEN_REQUEST)
                    
            elif (len(Cont.CSMA.activeQ)==G.NUM_CHAN) and (not (Cont.Channel.activeQ)==G.NUM_CHAN):
                for D in Cont.CSMA.activeQ:
                    #print self.ID, 'is interrupting!'
                    self.interrupt(D)
                    yield hold,self,random.expovariate(1/G.MEAN_BACKOFF)

def poisson_probability(actual, mean):
    # naive:   math.exp(-mean) * mean**actual / factorial(actual)

    # iterative, to keep the components from getting too large or small:
    p = math.exp(-mean)
    for i in xrange(actual):
        p *= mean
        p /= i+1
    return p





for run in range(50):
    for load in range(100):
        print load
        initialize()
        for i in range(G.NUM_DEVICE):
            D = Device(i)
            Cont.DeviceList.append(D)
            activate(Cont.DeviceList[i],Cont.DeviceList[i].execute(),at=0.0)
        simulate(until=G.MAX_TIME)
        G.ySeries[load] += G.Count
        G.Count = 0

for load in G.ySeries:
    G.endSeries.append(load/50)

pyl.plot(range(100),G.endSeries)
pyl.show()

        