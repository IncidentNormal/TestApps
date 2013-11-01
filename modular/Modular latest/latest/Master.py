'''
Created on Oct 29, 2010

@author: duncantait
'''
from SimPy.SimulationTrace import *
import MHS as M
import ALE as A
import Env as E

initialize()

for i in range(E.G.num_nodes):
    Mi = M.Instantiate(i)
    E.Env.Environment.MHS_nodes.append(Mi)
    Ai = A.Instantiate(i)
    E.Env.Environment.ALE_nodes.append(Ai)
for i in range(E.G.num_nodes):
    E.Env.Environment.MHS_nodes[i].initComponents()
    E.Env.Environment.ALE_nodes[i].initComponents()
for i in range(E.G.num_nodes):
    E.Env.Environment.MHS_nodes[i].activate()
    E.Env.Environment.ALE_nodes[i].activate()

simulate(until=1000)
print 'done'