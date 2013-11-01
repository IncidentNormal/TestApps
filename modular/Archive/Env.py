'''
Created on Oct 28, 2010

@author: duncantait
'''

#Environment (super)class - interfaces to all Tx and provides data as the physical Medium
#Doubles as the Simulation environment - providing Global variables and Global data structures

from SimPy.SimulationTrace import *
import random

class G(): #Global variables for simulation
    num_chans = 10
    num_nodes = 10
    max_bitrate = 398

class Environment(Process):
    def __init__(self):
        Process.__init__(self)
        self.channels = []
        self.nodes_chans_LQA = []
        for i in G.num_chans:
            self.channels.append(Store(capacity=1))
            for j in self.nodes: #clean this up, this one has all channels for each node (not as a grid tho, durr)
                self.nodes_chans_LQA.append(random.random()) #LQA
                
    #What we actually need is a 3 dimensional grid of Nodes:Channels:Nodes, so each Node has an LQA value for
    #each other Node, and for each channel.
            
    def execute(self):
        while True:
            yield hold, self, random.uniform(1,10)
            for i in range(len(self.nodes_chans_LQA)):
                self.nodes_chans_LQA[i] = random.random()
    
    #So whenever a signal is sent, it accesses the LQA on the 3D grid for that particular transaction, and then
    #copies it to it's own LQA table (future step...)
    #Obviously, this changing over time algorithm needs to be a bit better! Look at the sin wave examples 
    #from Grapher, so long-term, mid-term and short term changes (frequency), with low-magnitude noise throughout 

class dataStruct():
    def __init__(self, origin=-1, destination=-1, type=-1, chan=-1, size=-1, signal_time=-1, LQA=-1):  
        self.origin = origin
        self.destination = destination
        self.type = type
        self.chan = chan
        self.size = size
        self.signal_time = signal_time
        self.LQA = LQA
        
class dataType():
    CALL = 1
    RESPONSE = 2
    ACK = 3
    DATA = 4
 
class _Env():
    def __init__(self):
        self.G = G()
        self.Environment = Environment()
       
Env = _Env() 
        
        